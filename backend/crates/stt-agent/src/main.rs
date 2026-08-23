//! STT agent — real speech recognition over the NATS mesh.
//!
//! Dual-path fan-out:
//!   * **fast path** (`tiny.en`)  -> speculative partial hypotheses on
//!     `audio.perception`, plus keyword-triggered `audio.stop` for barge-in.
//!   * **accurate path** (`base.en`) -> the final transcript on `chat.input`.
//!
//! Whisper is an utterance model, so inbound PCM is buffered and segmented by an
//! energy endpointer (`audio::Endpointer`) before recognition. Inference is
//! CPU-bound and therefore runs on dedicated workers: the NATS receive loop only
//! decodes, buffers and dispatches, so audio ingestion is never blocked by a
//! transcription.

mod audio;
mod sensevoice;
mod whisper;

use anyhow::{Context, Result};
use async_nats::Message;
use bytes::Bytes;
use contracts::{
    topics, AmbientNoiseTelemetry, AudioPerception, AudioStop, ChatInput, ChatInputMetadata,
    JsonMap, LatencyHop, LatencyMetadata, SpeculativeIntent, UserVoiceProperties,
    HEADER_LATENCY_META,
};
use futures_util::StreamExt;
use serde_json::json;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::{mpsc, Mutex};
use tracing::{error, info, warn};
use uuid::Uuid;

use audio::{Endpointer, VadEvent};
use sensevoice::SenseVoiceModel;
use whisper::WhisperModel;

#[derive(Debug, Clone, PartialEq, Eq)]
enum Backend {
    Whisper,
    Mock,
}

#[derive(Debug, Clone)]
struct SttConfig {
    nats_url: String,
    backend: Backend,
    /// Only consulted when `backend == Mock`.
    mock_transcript: Option<String>,
    model_dir: PathBuf,
    fast_model: String,
    accurate_model: String,
    /// SenseVoice model directory. When it holds a usable model, SenseVoice serves
    /// the fast path and the agent perceives emotion; otherwise the fast path falls
    /// back to `fast_model` (Whisper) and the agent hears words but not tone.
    sensevoice_dir: PathBuf,
    /// Set `STT_SENSEVOICE=off` to force the Whisper fast path even when a
    /// SenseVoice model is present.
    sensevoice_enabled: bool,
    language: String,
    /// Used only when the inbound message carries no sample_rate header.
    fallback_sample_rate: u32,
    endpoint_silence_ms: f64,
    min_speech_ms: f64,
    partial_interval_ms: f64,
    max_utterance_secs: f64,
}

impl SttConfig {
    fn from_env() -> Self {
        let backend = match env_or("STT_BACKEND", "whisper").to_lowercase().as_str() {
            "mock" => Backend::Mock,
            _ => Backend::Whisper,
        };

        Self {
            nats_url: env_or("NATS_URL", "nats://127.0.0.1:4222"),
            backend,
            mock_transcript: std::env::var("RUST_STT_MOCK_TRANSCRIPT")
                .ok()
                .filter(|s| !s.trim().is_empty()),
            model_dir: PathBuf::from(env_or("STT_MODEL_DIR", "/app/models/whisper")),
            fast_model: env_or("STT_FAST_MODEL", "tiny.en"),
            accurate_model: env_or("STT_ACCURATE_MODEL", "base.en"),
            sensevoice_dir: PathBuf::from(env_or("STT_SENSEVOICE_DIR", "/app/models/sensevoice")),
            sensevoice_enabled: !matches!(
                env_or("STT_SENSEVOICE", "on").to_lowercase().as_str(),
                "off" | "false" | "0"
            ),
            language: env_or("STT_LANGUAGE", "en"),
            fallback_sample_rate: parse_env("STT_TARGET_SAMPLE_RATE", 16_000),
            endpoint_silence_ms: parse_env("STT_ENDPOINT_SILENCE_MS", 700.0),
            min_speech_ms: parse_env("STT_MIN_SPEECH_MS", 250.0),
            partial_interval_ms: parse_env("STT_PARTIAL_INTERVAL_MS", 500.0),
            max_utterance_secs: parse_env("STT_MAX_UTTERANCE_SECS", 30.0),
        }
    }
}

fn env_or(name: &str, fallback: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| fallback.to_string())
}

fn parse_env<T: std::str::FromStr>(name: &str, fallback: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(fallback)
}

/// A unit of work for an inference worker.
struct Job {
    pcm_16k: Vec<f32>,
    utterance_id: String,
    latency: Option<LatencyMetadata>,
}

/// A one-slot, latest-wins handoff to the speculative partial worker.
///
/// Partials are disposable by design: if the fast model cannot keep up, the only
/// hypothesis worth transcribing is the newest one. A bounded channel cannot
/// express that — `try_send` fails on a full channel and thereby keeps the
/// *oldest* queued job — so this replaces the pending job instead of rejecting
/// the new one.
#[derive(Default)]
struct PartialSlot {
    pending: std::sync::Mutex<Option<Job>>,
    ready: tokio::sync::Notify,
}

impl PartialSlot {
    /// Overwrite any pending job. Never blocks and never discards the newest job.
    fn offer(&self, job: Job) {
        if let Ok(mut pending) = self.pending.lock() {
            *pending = Some(job);
        }
        self.ready.notify_one();
    }

    /// Wait for the most recently offered job.
    async fn take(&self) -> Job {
        loop {
            // `Notify` holds a permit if `offer` ran before we registered, so a job
            // offered between these two lines wakes the next `notified()` at once.
            if let Some(job) = self.pending.lock().ok().and_then(|mut p| p.take()) {
                return job;
            }
            self.ready.notified().await;
        }
    }
}

struct SttState {
    endpointer: Endpointer,
    /// Accumulated mono samples at the *source* rate; resampled at inference time.
    buffer: Vec<f32>,
    source_rate: u32,
    utterance_id: String,
    utterance_latency: Option<LatencyMetadata>,
    last_partial_at: f64,
    last_noise_publish: f64,
    /// audit/ROADMAP.md P1-4: the keyword duck is a *hint*, not the arbiter --
    /// the brain's `is_speculative_stop_confirmed` (decision.py) is the one
    /// component allowed to turn it into a real abort. Partials are cumulative
    /// re-transcriptions of the same utterance (P2-9), so a keyword that
    /// appears once stays in every later partial; without this, each of those
    /// re-published a fresh speculative `audio.stop`. Tracks which
    /// `utterance_id` has already fired one, so a new one only fires when a
    /// new utterance starts.
    speculative_fired_for: Option<String>,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let config = SttConfig::from_env();

    let client = async_nats::connect(config.nats_url.clone())
        .await
        .with_context(|| format!("connect to NATS at {}", config.nats_url))?;
    let jetstream = async_nats::jetstream::new(client.clone());
    let mut subscriber = client.subscribe(topics::AUDIO_INBOUND).await?;

    let state = Arc::new(Mutex::new(SttState {
        endpointer: Endpointer::new(config.endpoint_silence_ms, config.min_speech_ms),
        buffer: Vec::new(),
        source_rate: config.fallback_sample_rate,
        utterance_id: Uuid::new_v4().to_string(),
        utterance_latency: None,
        last_partial_at: 0.0,
        last_noise_publish: 0.0,
        speculative_fired_for: None,
    }));

    // Latest-wins slot for partials: if the fast model is still busy, a newer
    // partial supersedes the queued one — stale speculative text is worse than
    // none. This was previously an `mpsc::channel(1)` + `try_send`, which does the
    // *opposite*: `try_send` on a full channel rejects the new job and keeps the
    // older one, so an overloaded fast path published hypotheses that lagged the
    // speaker instead of skipping to the current one.
    let partial_slot = Arc::new(PartialSlot::default());
    // Finals must not be dropped; they drive cognition.
    let (final_tx, final_rx) = mpsc::channel::<Job>(8);

    match config.backend {
        Backend::Mock => {
            let transcript = config.mock_transcript.clone().context(
                "STT_BACKEND=mock but RUST_STT_MOCK_TRANSCRIPT is empty. Set a transcript, \
                 or use STT_BACKEND=whisper for real recognition.",
            )?;
            warn!(
                transcript = %transcript,
                "stt-agent running in MOCK mode: inbound audio content is ignored and a fixed \
                 string is replayed. Downstream chat.input is NOT real perception."
            );
            spawn_mock_workers(jetstream.clone(), partial_slot.clone(), final_rx, transcript);
        }
        Backend::Whisper => {
            info!(
                accurate = %config.accurate_model,
                dir = %config.model_dir.display(),
                "resolving whisper models"
            );
            let accurate_path =
                whisper::ensure_model(&config.model_dir, &config.accurate_model).await?;
            let accurate =
                Arc::new(WhisperModel::load(&accurate_path, "accurate", &config.language)?);

            let fast = Arc::new(load_fast_path(&config).await?);
            let hears_emotion = matches!(*fast, FastPath::SenseVoice(_));

            spawn_partial_worker(
                jetstream.clone(),
                partial_slot.clone(),
                fast,
                state.clone(),
            );
            spawn_final_worker(jetstream.clone(), final_rx, accurate);
            info!(
                hears_emotion,
                "stt-agent online with real recognition (dual-path)"
            );
        }
    }

    info!("rust stt-agent subscribed to {}", topics::AUDIO_INBOUND);

    while let Some(message) = subscriber.next().await {
        if let Err(err) = handle_audio_inbound(
            &config,
            &jetstream,
            message,
            state.clone(),
            &partial_slot,
            &final_tx,
        )
        .await
        {
            error!("stt-agent failed to process audio.inbound: {err:#}");
        }
    }

    Ok(())
}

/// The model serving the speculative fast path.
///
/// SenseVoice is preferred because it perceives *how* the user sounds, not just
/// what they said — the input HNNA's affect pillar was designed around and has
/// been starved of since the Rust migration. Whisper is the fallback when no
/// SenseVoice model is provisioned: it keeps barge-in working, but the agent stays
/// deaf to tone.
enum FastPath {
    SenseVoice(Arc<SenseVoiceModel>),
    Whisper(Arc<WhisperModel>),
}

impl FastPath {
    /// Transcribe, and read acoustic affect if this model can.
    fn perceive(&self, pcm_16k: &[f32]) -> Result<sensevoice::Perception> {
        match self {
            FastPath::SenseVoice(model) => model.perceive(pcm_16k),
            FastPath::Whisper(model) => Ok(sensevoice::Perception {
                text: model.transcribe(pcm_16k)?,
                // Whisper classifies neither emotion nor audio events. These stay
                // absent rather than defaulting: `None` means "no acoustic estimate",
                // which the Python state machine treats differently from a genuine
                // neutral reading. Defaulting to 0.0 here would flatten the agent's
                // mood toward zero on every single utterance.
                emotion: None,
                emotional_bias: None,
                events: Vec::new(),
            }),
        }
    }

    fn label(&self) -> &'static str {
        match self {
            FastPath::SenseVoice(_) => "sensevoice",
            FastPath::Whisper(_) => "whisper-fast",
        }
    }
}

/// Transcribe one utterance and publish the final transcript onto `chat.input`.
async fn run_final_job(
    jetstream: &async_nats::jetstream::Context,
    model: &Arc<WhisperModel>,
    job: Job,
) {
    let model = model.clone();
    let pcm = job.pcm_16k;
    let started = now_seconds();

    let result = tokio::task::spawn_blocking(move || model.transcribe(&pcm)).await;

    let text = match result {
        Ok(Ok(text)) => text,
        Ok(Err(err)) => {
            error!("whisper inference error: {err:#}");
            return;
        }
        Err(err) => {
            error!("whisper worker panicked: {err}");
            return;
        }
    };

    if text.trim().is_empty() {
        return;
    }

    let elapsed_ms = (now_seconds() - started) * 1000.0;
    info!(text = %text, took_ms = elapsed_ms, "final transcript");
    if let Err(err) = publish_final(jetstream, &text, &job.utterance_id, job.latency, "whisper").await
    {
        error!("stt-agent failed to publish transcript: {err:#}");
    }
}

/// Run the speculative fast path and publish onto `audio.perception`.
async fn run_partial_job(
    jetstream: &async_nats::jetstream::Context,
    fast: &Arc<FastPath>,
    state: &Arc<Mutex<SttState>>,
    job: Job,
) {
    let model = fast.clone();
    let pcm = job.pcm_16k;
    let started = now_seconds();

    let result = tokio::task::spawn_blocking(move || model.perceive(&pcm)).await;

    let perception = match result {
        Ok(Ok(perception)) => perception,
        Ok(Err(err)) => {
            error!(model = fast.label(), "fast-path inference error: {err:#}");
            return;
        }
        Err(err) => {
            error!(model = fast.label(), "fast-path worker panicked: {err}");
            return;
        }
    };

    // Events are perception even without words: a laugh or a cough carries affect
    // and has no transcript. Dropping on empty text alone would discard them.
    if perception.text.trim().is_empty() && perception.events.is_empty() {
        return;
    }

    let elapsed_ms = (now_seconds() - started) * 1000.0;

    // Inference outlives the utterance it came from: by now the endpointer may have
    // closed that turn and rotated `utterance_id`. Publishing anyway would put a
    // hypothesis for finished speech on audio.perception, whose barge-in path could
    // then emit audio.stop against whatever the agent is saying *now*.
    if !is_current_utterance(state, &job.utterance_id).await {
        info!(
            took_ms = elapsed_ms,
            "discarding partial for an utterance that already closed"
        );
        return;
    }

    if let Err(err) =
        publish_partial(jetstream, &perception, &job.utterance_id, Some(state)).await
    {
        error!("stt-agent failed to publish perception: {err:#}");
    }
}

/// Whether `utterance_id` is still the utterance the endpointer has open.
async fn is_current_utterance(state: &Arc<Mutex<SttState>>, utterance_id: &str) -> bool {
    state.lock().await.utterance_id == utterance_id
}

/// Claim the one speculative-duck fire allowed per utterance. Returns `true`
/// (and records the claim) the first time it is called for `utterance_id`;
/// every later call for the same utterance returns `false`.
async fn claim_speculative_fire(state: &Arc<Mutex<SttState>>, utterance_id: &str) -> bool {
    let mut guard = state.lock().await;
    if guard.speculative_fired_for.as_deref() == Some(utterance_id) {
        false
    } else {
        guard.speculative_fired_for = Some(utterance_id.to_string());
        true
    }
}

/// Choose the fast-path model: SenseVoice when available, Whisper otherwise.
///
/// The fallback is deliberate rather than fatal — barge-in must keep working on a
/// host with no SenseVoice model — but it is *loud*, because the difference is not
/// cosmetic: without SenseVoice the agent cannot perceive tone at all, and the
/// entire acoustic half of the affect pillar stays dark.
async fn load_fast_path(config: &SttConfig) -> Result<FastPath> {
    if config.sensevoice_enabled {
        match SenseVoiceModel::load(&config.sensevoice_dir, &config.language) {
            Ok(model) => return Ok(FastPath::SenseVoice(Arc::new(model))),
            Err(err) => sensevoice::warn_if_unavailable(&config.sensevoice_dir, &err),
        }
    } else {
        warn!(
            "STT_SENSEVOICE is off: the fast path will use Whisper and the agent will \
             not perceive acoustic emotion or audio events."
        );
    }

    info!(fast = %config.fast_model, "falling back to the Whisper fast path");
    let fast_path = whisper::ensure_model(&config.model_dir, &config.fast_model).await?;
    Ok(FastPath::Whisper(Arc::new(WhisperModel::load(
        &fast_path,
        "fast",
        &config.language,
    )?)))
}

fn spawn_final_worker(
    jetstream: async_nats::jetstream::Context,
    mut rx: mpsc::Receiver<Job>,
    model: Arc<WhisperModel>,
) {
    tokio::spawn(async move {
        while let Some(job) = rx.recv().await {
            run_final_job(&jetstream, &model, job).await;
        }
    });
}

fn spawn_partial_worker(
    jetstream: async_nats::jetstream::Context,
    slot: Arc<PartialSlot>,
    fast: Arc<FastPath>,
    state: Arc<Mutex<SttState>>,
) {
    tokio::spawn(async move {
        loop {
            let job = slot.take().await;
            run_partial_job(&jetstream, &fast, &state, job).await;
        }
    });
}

/// Mock workers keep the deterministic path available for CI without pulling
/// models, while still exercising the real buffering/endpointing pipeline.
fn spawn_mock_workers(
    jetstream: async_nats::jetstream::Context,
    partial_slot: Arc<PartialSlot>,
    mut final_rx: mpsc::Receiver<Job>,
    transcript: String,
) {
    let js = jetstream.clone();
    let text = transcript.clone();
    tokio::spawn(async move {
        loop {
            let job = partial_slot.take().await;
            // No emotion or events: a mock must never fabricate acoustic affect that
            // would drift the agent's real mood.
            let perception = sensevoice::Perception {
                text: text.clone(),
                ..Default::default()
            };
            if let Err(err) = publish_partial(&js, &perception, &job.utterance_id, None).await {
                error!("mock partial publish failed: {err:#}");
            }
        }
    });
    tokio::spawn(async move {
        while let Some(job) = final_rx.recv().await {
            // source="mock", never "whisper": downstream must be able to tell a
            // scripted string from real recognition.
            if let Err(err) =
                publish_final(&jetstream, &transcript, &job.utterance_id, job.latency, "mock").await
            {
                error!("mock final publish failed: {err:#}");
            }
        }
    });
}

/// Build the `audio.perception` message for a fast-path hypothesis.
///
/// Pure so its wire shape is testable: the acoustic-affect consumer reads
/// `metadata`, NOT the top-level fields. `CognitiveService._on_audio_perception`
/// takes `data["metadata"]` and hands it to
/// `StateService.apply_sensory_perception`, which looks up "emotional_bias" and
/// "events" there. The pre-migration Python STT agent published *both* locations
/// (`metadata={**perception_data}` plus `paralinguistic_events=...`); the Rust
/// rewrite kept only the top-level field, so even a model that did classify
/// emotion would have had it silently dropped on the floor. Populating both is
/// what actually reconnects the wire.
fn build_partial_perception(
    heard: &sensevoice::Perception,
    utterance_id: &str,
) -> (AudioPerception, Option<SpeculativeIntent>) {
    let text = heard.text.as_str();

    let mut metadata_map = JsonMap::new();
    metadata_map.insert("text".to_string(), json!(text));
    metadata_map.insert("is_partial".to_string(), json!(true));
    metadata_map.insert("events".to_string(), json!(heard.events));
    if let Some(emotion) = &heard.emotion {
        metadata_map.insert("emotion".to_string(), json!(emotion));
    }
    // Only present when a model genuinely estimated it. An absent key and an
    // explicit 0.0 mean different things downstream: absence is "no acoustic
    // evidence" and is skipped, while 0.0 is a real neutral reading that gets
    // blended. Writing 0.0 for "we don't know" would drag mood toward zero on every
    // perception and erase the affect semantic appraisal just established.
    if let Some(bias) = heard.emotional_bias {
        metadata_map.insert("emotional_bias".to_string(), json!(bias));
    }

    let speculative = build_speculative_intent(text, utterance_id);
    let intent = speculative.as_ref().map(|s| s.name.clone());
    let keywords = speculative
        .as_ref()
        .map(|s| s.keywords.clone())
        .unwrap_or_default();
    let confidence = speculative.as_ref().map(|s| s.confidence).unwrap_or(0.7);

    let perception = AudioPerception {
        text: text.to_string(),
        intent,
        intent_type: "CONVERSATIONAL".to_string(),
        keywords,
        confidence,
        snr: 0.0,
        paralinguistic_events: heard.events.clone(),
        speculative_intent: speculative.clone(),
        metadata: metadata_map,
        timestamp: now_seconds(),
        utterance_id: Some(utterance_id.to_string()),
    };

    (perception, speculative)
}

async fn publish_partial(
    jetstream: &async_nats::jetstream::Context,
    heard: &sensevoice::Perception,
    utterance_id: &str,
    state: Option<&Arc<Mutex<SttState>>>,
) -> Result<()> {
    let (perception, speculative) = build_partial_perception(heard, utterance_id);

    jetstream
        .publish(
            topics::AUDIO_PERCEPTION,
            Bytes::from(serde_json::to_vec(&perception)?),
        )
        .await?
        .await?;

    if let Some(spec) = speculative {
        // P1-4: only ever a duck, never the abort -- decision.py's
        // `is_speculative_stop_confirmed` is the sole component allowed to
        // turn this into a real interruption. Scoped to fire once per
        // utterance (see `speculative_fired_for`); mock mode has no `state`
        // and always fires, which is fine -- it never drives production
        // barge-in.
        let should_fire = match state {
            Some(state) => claim_speculative_fire(state, utterance_id).await,
            None => true,
        };
        if should_fire {
            let stop = AudioStop {
                interrupt: true,
                speculative: true,
                reason: None,
                command_text: None,
                intent: Some(spec.name.clone()),
                intent_type: "VOICE_INTERRUPTION".to_string(),
                keywords: spec.keywords.clone(),
                confidence: spec.confidence,
                perception_text: Some(spec.text.clone()),
                utterance_id: spec.utterance_id.clone(),
                turn_id: None,
            };
            jetstream
                .publish(topics::AUDIO_STOP, Bytes::from(serde_json::to_vec(&stop)?))
                .await?
                .await?;
        }
    }

    Ok(())
}

async fn publish_final(
    jetstream: &async_nats::jetstream::Context,
    text: &str,
    utterance_id: &str,
    latency: Option<LatencyMetadata>,
    source: &str,
) -> Result<()> {
    let latency_metadata = append_latency(latency, topics::CHAT_INPUT);
    let chat = ChatInput {
        text: text.to_string(),
        utterance_id: Some(utterance_id.to_string()),
        turn_id: None,
        metadata: ChatInputMetadata {
            // Provenance must reflect what actually produced the text: a mock run
            // labelled "whisper" is precisely the defect this rewrite removed.
            source: source.to_string(),
            confidence: 0.9,
            utterance_id: Some(utterance_id.to_string()),
        },
        latency_metadata: Some(latency_metadata),
    };

    jetstream
        .publish(topics::CHAT_INPUT, Bytes::from(serde_json::to_vec(&chat)?))
        .await?
        .await?;
    Ok(())
}

async fn handle_audio_inbound(
    config: &SttConfig,
    jetstream: &async_nats::jetstream::Context,
    message: Message,
    state: Arc<Mutex<SttState>>,
    partial_slot: &Arc<PartialSlot>,
    final_tx: &mpsc::Sender<Job>,
) -> Result<()> {
    let metadata = metadata_from_headers(&message);
    let channels = metadata.as_ref().and_then(|m| m.channels).unwrap_or(1) as usize;
    let header_rate = metadata.as_ref().and_then(|m| m.sample_rate);

    let chunk = audio::decode_mono_f32(&message.payload, channels.max(1));
    if chunk.is_empty() {
        return Ok(());
    }

    let source_rate = header_rate.unwrap_or(config.fallback_sample_rate).max(1);
    let chunk_rms = audio::rms(&chunk);
    let chunk_ms = (chunk.len() as f64 / source_rate as f64) * 1000.0;

    let mut guard = state.lock().await;
    guard.source_rate = source_rate;
    guard.buffer.extend_from_slice(&chunk);
    if guard.utterance_latency.is_none() {
        guard.utterance_latency = metadata.clone();
    }

    let event = guard.endpointer.push(chunk_rms, chunk_ms);
    let now = now_seconds();

    // Ambient noise telemetry (throttled).
    if now - guard.last_noise_publish >= 0.5 {
        guard.last_noise_publish = now;
        let floor = guard.endpointer.noise_floor();
        let noise_floor_db = if floor > 0.0 {
            20.0 * floor.log10()
        } else {
            -100.0
        };
        let telemetry = AmbientNoiseTelemetry {
            rms_energy: floor,
            noise_floor_db,
            timestamp: now,
        };
        // Publish, but do not await the JetStream ack (see the voice-properties
        // publish below for why).
        let _ = jetstream
            .publish(
                topics::AMBIENT_NOISE_TELEMETRY,
                Bytes::from(serde_json::to_vec(&telemetry)?),
            )
            .await?;
    }

    // Voice properties, derived at the true source rate (previously these used a
    // hardcoded 16 kHz regardless of the real rate, skewing pitch by the ratio).
    let voice_properties = UserVoiceProperties {
        pitch_f0: estimate_f0(&chunk, source_rate),
        energy_rms: chunk_rms,
        tempo_wpm: estimate_tempo_wpm(&chunk),
        timestamp: now,
    };
    // `.publish().await` hands the message to the connection; the returned
    // PublishAckFuture is deliberately *not* awaited. Awaiting it costs a NATS
    // round-trip on every inbound chunk (~50/sec at 20ms frames), and this loop is
    // the only consumer of audio.inbound — a slow or backed-up JetStream would
    // stall audio ingestion itself, losing the very speech we are here to hear.
    // These are ephemeral observability samples superseded by the next chunk, so
    // delivery confirmation buys nothing worth that risk.
    let _ = jetstream
        .publish(
            topics::USER_VOICE_PROPERTIES,
            Bytes::from(serde_json::to_vec(&voice_properties)?),
        )
        .await?;

    // Guard against an unbounded buffer if the endpointer never fires (e.g. a
    // continuously noisy room): force a cut at max_utterance_secs.
    let buffered_secs = guard.buffer.len() as f64 / source_rate as f64;
    let force_cut = buffered_secs >= config.max_utterance_secs;

    match event {
        VadEvent::Silence if !force_cut => {
            // Keep only a short pre-roll so speech onset isn't clipped.
            let preroll = (source_rate as f64 * 0.3) as usize;
            if guard.buffer.len() > preroll {
                let excess = guard.buffer.len() - preroll;
                guard.buffer.drain(..excess);
            }
            // The audio this latency metadata described has just been discarded, so
            // its provenance no longer applies to anything buffered. Re-anchor it to
            // the current chunk, which is what the retained pre-roll now consists of.
            // Left stale, the first chunk after startup would date the utterance
            // forever: someone speaking an hour into an idle session produced a
            // chat.input whose capture timestamp was an hour old, inflating every
            // downstream latency measurement by the length of the silence.
            guard.utterance_latency = metadata.clone();
        }
        VadEvent::SpeechContinues if !force_cut => {
            // `SpeechContinues` fires from the first voiced chunk, before the
            // endpointer believes this is speech at all. Transcribing that would
            // spend the fast model on a blip and, worse, let its hypothesis reach
            // the barge-in path — interrupting the agent for a cough that the
            // endpointer goes on to reject as noise.
            let confirmed = guard.endpointer.speech_confirmed();
            if confirmed && now - guard.last_partial_at >= config.partial_interval_ms / 1000.0 {
                guard.last_partial_at = now;
                let pcm = guard.buffer.clone();
                let utt = guard.utterance_id.clone();
                let rate = source_rate;
                drop(guard);

                if let Ok(pcm_16k) = audio::resample_to_16k(&pcm, rate) {
                    // Latest-wins: replaces any hypothesis the fast model has not
                    // started yet, rather than being dropped in favour of it.
                    partial_slot.offer(Job {
                        pcm_16k,
                        utterance_id: utt,
                        latency: None,
                    });
                }
                return Ok(());
            }
        }
        _ => {
            // Endpoint (or forced cut): close the utterance and transcribe it.
            let pcm = std::mem::take(&mut guard.buffer);
            let utt = guard.utterance_id.clone();
            let latency = guard.utterance_latency.take();
            guard.utterance_id = Uuid::new_v4().to_string();
            guard.last_partial_at = 0.0;
            let rate = source_rate;
            drop(guard);

            let pcm_16k = audio::resample_to_16k(&pcm, rate)?;
            if !pcm_16k.is_empty() {
                info!(
                    secs = pcm_16k.len() as f64 / 16_000.0,
                    forced = force_cut,
                    "utterance endpointed; transcribing"
                );
                final_tx
                    .send(Job {
                        pcm_16k,
                        utterance_id: utt,
                        latency,
                    })
                    .await
                    .ok();
            }
        }
    }

    Ok(())
}

/// Autocorrelation pitch estimate over the 80-400 Hz band, at the true rate.
fn estimate_f0(samples: &[f32], sample_rate: u32) -> f64 {
    let min_lag = (sample_rate as f64 / 400.0) as usize;
    let max_lag = (sample_rate as f64 / 80.0) as usize;
    if samples.len() <= max_lag || min_lag == 0 {
        return 150.0;
    }

    let mut best_lag = 0usize;
    let mut best_corr = -1.0f64;

    for lag in min_lag..=max_lag {
        let mut corr = 0.0f64;
        let mut norm1 = 0.0f64;
        let mut norm2 = 0.0f64;
        for i in 0..(samples.len() - lag) {
            let x = samples[i] as f64;
            let y = samples[i + lag] as f64;
            corr += x * y;
            norm1 += x * x;
            norm2 += y * y;
        }
        if norm1 > 0.0 && norm2 > 0.0 {
            let normalized = corr / (norm1 * norm2).sqrt();
            if normalized > best_corr {
                best_corr = normalized;
                best_lag = lag;
            }
        }
    }

    if best_corr > 0.3 && best_lag > 0 {
        sample_rate as f64 / best_lag as f64
    } else {
        150.0
    }
}

fn estimate_tempo_wpm(samples: &[f32]) -> f64 {
    if samples.is_empty() {
        return 120.0;
    }
    let mut zero_crossings = 0usize;
    for i in 1..samples.len() {
        if (samples[i - 1] >= 0.0) != (samples[i] >= 0.0) {
            zero_crossings += 1;
        }
    }
    let zcr = zero_crossings as f64 / samples.len() as f64;
    120.0 + (zcr * 200.0).min(60.0)
}

fn metadata_from_headers(message: &Message) -> Option<LatencyMetadata> {
    let header_value = message.headers.as_ref()?.get(HEADER_LATENCY_META)?;
    serde_json::from_str(header_value.as_str()).ok()
}

fn append_latency(metadata: Option<LatencyMetadata>, subject: &str) -> LatencyMetadata {
    let now = now_seconds();
    let mut metadata = metadata.unwrap_or_else(|| LatencyMetadata {
        start_time: now,
        hops: Vec::new(),
        source: "stt_agent".to_string(),
        channels: None,
        sample_rate: None,
    });
    metadata.hops.push(LatencyHop {
        agent: "stt_agent".to_string(),
        subject: subject.to_string(),
        timestamp: now,
    });
    metadata
}

fn build_speculative_intent(text: &str, utterance_id: &str) -> Option<SpeculativeIntent> {
    let normalized = text
        .to_lowercase()
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { ' ' })
        .collect::<String>();
    let tokens = normalized
        .split_whitespace()
        .collect::<std::collections::HashSet<_>>();
    // audit/ROADMAP.md P1-4 (M3-A13): this used to include "alex"/"friend" --
    // a persona name hardcoded into a generic crate. Deleted regardless of
    // which arbiter survives; this list is only ever a duck hint now (see
    // `speculative_fired_for`), never the abort.
    let keywords = ["stop", "wait", "hold", "no", "wrong", "quiet"]
        .iter()
        .copied()
        .filter(|keyword| tokens.contains(keyword))
        .map(ToString::to_string)
        .collect::<Vec<_>>();

    if keywords.is_empty() {
        return None;
    }

    Some(SpeculativeIntent {
        name: "SPECULATIVE_STOP".to_string(),
        keywords,
        confidence: 0.9,
        text: text.to_string(),
        timestamp: now_seconds(),
        utterance_id: Some(utterance_id.to_string()),
    })
}

#[allow(dead_code)]
fn build_audio_perception(text: &str, speculative: &SpeculativeIntent) -> AudioPerception {
    let mut metadata = JsonMap::new();
    metadata.insert("text".to_string(), json!(text));
    metadata.insert("confidence".to_string(), json!(speculative.confidence));

    AudioPerception {
        text: text.to_string(),
        intent: Some(speculative.name.clone()),
        intent_type: "COMMAND".to_string(),
        keywords: speculative.keywords.clone(),
        confidence: speculative.confidence,
        snr: 0.0,
        paralinguistic_events: Vec::new(),
        speculative_intent: Some(speculative.clone()),
        metadata,
        timestamp: speculative.timestamp,
        utterance_id: speculative.utterance_id.clone(),
    }
}

fn now_seconds() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pcm_bytes_are_never_parsed_as_text() {
        let decoded = audio::decode_mono_f32(br#"{"audio":"legacy-json"}"#, 1);
        assert!(!decoded.is_empty());
        assert!(build_speculative_intent("", "utt-1").is_none());
    }

    fn job(utterance_id: &str) -> Job {
        Job {
            pcm_16k: vec![0.0; 4],
            utterance_id: utterance_id.to_string(),
            latency: None,
        }
    }

    /// The wire-shape regression this whole integration exists to prevent.
    ///
    /// Python's consumer chain is `CognitiveService._on_audio_perception` →
    /// `data["metadata"]` → `StateService.apply_sensory_perception` →
    /// `metadata["emotional_bias"]` / `metadata["events"]`. The post-migration Rust
    /// agent published emotion data (had it existed) only at the top level, where
    /// that chain never looks — a wire that inspected as connected but carried
    /// nothing. This test walks the serialized JSON exactly the way Python does.
    #[test]
    fn perception_carries_affect_where_python_reads_it() {
        let heard = sensevoice::Perception {
            text: "that is wonderful".into(),
            emotion: Some("HAPPY".into()),
            emotional_bias: Some(0.4),
            events: vec!["Laughter".into()],
        };
        let (perception, _) = build_partial_perception(&heard, "utt-1");
        let wire: serde_json::Value =
            serde_json::from_slice(&serde_json::to_vec(&perception).unwrap()).unwrap();

        // Python: data.get("metadata", {})
        let metadata = &wire["metadata"];
        assert_eq!(metadata["emotional_bias"], json!(0.4));
        assert_eq!(metadata["events"], json!(["Laughter"]));
        assert_eq!(metadata["emotion"], json!("HAPPY"));
        assert_eq!(metadata["is_partial"], json!(true));
        // The top-level contract field must ALSO be populated.
        assert_eq!(wire["paralinguistic_events"], json!(["Laughter"]));
    }

    #[test]
    fn absent_emotion_is_an_absent_key_not_zero() {
        // `metadata.get("emotional_bias")` returning 0.0 and returning None steer
        // the Python state machine differently: 0.0 is blended into mood as a real
        // neutral reading, None is skipped. A Whisper fast path (no emotion model)
        // must therefore OMIT the key entirely, or every utterance would drag the
        // agent's mood toward zero — the exact bug fixed in 45e1a33.
        let heard = sensevoice::Perception {
            text: "hello there".into(),
            ..Default::default()
        };
        let (perception, _) = build_partial_perception(&heard, "utt-1");
        let wire: serde_json::Value =
            serde_json::from_slice(&serde_json::to_vec(&perception).unwrap()).unwrap();

        let metadata = wire["metadata"].as_object().unwrap();
        assert!(!metadata.contains_key("emotional_bias"));
        assert!(!metadata.contains_key("emotion"));
        assert_eq!(metadata["events"], json!([]));
    }

    #[tokio::test]
    async fn partial_slot_keeps_the_newest_hypothesis() {
        // The regression this guards: partials used to go through
        // `mpsc::channel(1)` + `try_send`, which drops the *new* job when the
        // channel is full and delivers the stale one. An overloaded fast path then
        // published hypotheses describing speech the user had already finished.
        let slot = PartialSlot::default();
        slot.offer(job("utt-old"));
        slot.offer(job("utt-newer"));
        slot.offer(job("utt-newest"));

        let received = slot.take().await;
        assert_eq!(
            received.utterance_id, "utt-newest",
            "the most recent partial must supersede queued ones"
        );
    }

    #[tokio::test]
    async fn partial_slot_wakes_a_waiting_worker() {
        let slot = Arc::new(PartialSlot::default());
        let waiter = slot.clone();
        let handle = tokio::spawn(async move { waiter.take().await });

        // Yield so the worker is parked in `take()` before anything is offered:
        // this exercises the notify path rather than the already-pending path.
        tokio::task::yield_now().await;
        slot.offer(job("utt-1"));

        let received = tokio::time::timeout(std::time::Duration::from_secs(5), handle)
            .await
            .expect("worker should be woken by offer")
            .expect("worker task should not panic");
        assert_eq!(received.utterance_id, "utt-1");
    }

    #[test]
    fn downmixes_multichannel_pcm_like_python_agent() {
        let stereo_samples = [1000_i16, -1000, 3000, 1000];
        let mut bytes = Vec::new();
        for sample in stereo_samples {
            bytes.extend_from_slice(&sample.to_le_bytes());
        }

        let mono = audio::decode_mono_f32(&bytes, 2);
        assert_eq!(mono.len(), 2);
        assert!(mono[0].abs() < 0.001);
        assert!((mono[1] - (2000.0 / i16::MAX as f32)).abs() < 0.001);
    }

    #[test]
    fn speculative_stop_shape_matches_current_contract() {
        let spec = build_speculative_intent("stop now", "utt-1").unwrap();
        let perception = build_audio_perception("stop now", &spec);

        assert_eq!(perception.intent.as_deref(), Some("SPECULATIVE_STOP"));
        assert_eq!(perception.intent_type, "COMMAND");
        assert_eq!(perception.keywords, vec!["stop"]);
        assert_eq!(
            perception.speculative_intent.unwrap().utterance_id.as_deref(),
            Some("utt-1")
        );
    }

    #[test]
    fn speculative_stop_avoids_partial_keyword_matches() {
        assert!(build_speculative_intent("knowledge now", "utt-1").is_none());
    }

    fn test_state() -> Arc<Mutex<SttState>> {
        Arc::new(Mutex::new(SttState {
            endpointer: Endpointer::new(600.0, 200.0),
            buffer: Vec::new(),
            source_rate: 16000,
            utterance_id: "utt-1".to_string(),
            utterance_latency: None,
            last_partial_at: 0.0,
            last_noise_publish: 0.0,
            speculative_fired_for: None,
        }))
    }

    /// P1-4 (M3-A13): partials are cumulative re-transcriptions of the same
    /// utterance, so a keyword that appears once would otherwise still be
    /// present -- and re-detected -- in every partial after it. Only the
    /// first claim for a given utterance may succeed.
    #[tokio::test]
    async fn speculative_fire_is_claimed_once_per_utterance() {
        let state = test_state();
        assert!(claim_speculative_fire(&state, "utt-1").await);
        assert!(!claim_speculative_fire(&state, "utt-1").await);
        assert!(!claim_speculative_fire(&state, "utt-1").await);
    }

    #[tokio::test]
    async fn speculative_fire_claim_resets_on_a_new_utterance() {
        let state = test_state();
        assert!(claim_speculative_fire(&state, "utt-1").await);
        assert!(!claim_speculative_fire(&state, "utt-1").await);
        assert!(claim_speculative_fire(&state, "utt-2").await);
    }

    #[test]
    fn f0_tracks_a_known_tone_at_its_true_rate() {
        // 200 Hz sine at 48 kHz must read ~200 Hz, not 200*(16000/48000).
        let rate = 48_000u32;
        let freq = 200.0f64;
        let samples: Vec<f32> = (0..rate as usize / 2)
            .map(|i| {
                (2.0 * std::f64::consts::PI * freq * (i as f64 / rate as f64)).sin() as f32
            })
            .collect();
        let f0 = estimate_f0(&samples, rate);
        assert!((f0 - freq).abs() < 10.0, "expected ~{freq} Hz, got {f0}");
    }

    #[test]
    fn backend_defaults_to_whisper_not_mock() {
        // Guards the E1 regression: the deployed agent must not silently ship mocks.
        std::env::remove_var("STT_BACKEND");
        assert_eq!(SttConfig::from_env().backend, Backend::Whisper);
    }
}
