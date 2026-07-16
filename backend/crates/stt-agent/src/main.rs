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

struct SttState {
    endpointer: Endpointer,
    /// Accumulated mono samples at the *source* rate; resampled at inference time.
    buffer: Vec<f32>,
    source_rate: u32,
    utterance_id: String,
    utterance_latency: Option<LatencyMetadata>,
    last_partial_at: f64,
    last_noise_publish: f64,
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
    }));

    // Bounded(1) for partials: if the fast model is still busy, a newer partial
    // supersedes the queued one — stale speculative text is worse than none.
    let (partial_tx, partial_rx) = mpsc::channel::<Job>(1);
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
            spawn_mock_workers(jetstream.clone(), partial_rx, final_rx, transcript);
        }
        Backend::Whisper => {
            info!(
                fast = %config.fast_model,
                accurate = %config.accurate_model,
                dir = %config.model_dir.display(),
                "resolving whisper models"
            );
            let fast_path = whisper::ensure_model(&config.model_dir, &config.fast_model).await?;
            let accurate_path =
                whisper::ensure_model(&config.model_dir, &config.accurate_model).await?;

            let fast = Arc::new(WhisperModel::load(&fast_path, "fast", &config.language)?);
            let accurate =
                Arc::new(WhisperModel::load(&accurate_path, "accurate", &config.language)?);

            spawn_whisper_worker(jetstream.clone(), partial_rx, fast, PathKind::Partial);
            spawn_whisper_worker(jetstream.clone(), final_rx, accurate, PathKind::Final);
            info!("stt-agent online with real whisper recognition (dual-path)");
        }
    }

    info!("rust stt-agent subscribed to {}", topics::AUDIO_INBOUND);

    while let Some(message) = subscriber.next().await {
        if let Err(err) = handle_audio_inbound(
            &config,
            &jetstream,
            message,
            state.clone(),
            &partial_tx,
            &final_tx,
        )
        .await
        {
            error!("stt-agent failed to process audio.inbound: {err:#}");
        }
    }

    Ok(())
}

/// Which half of the dual-path fan-out a worker serves.
#[derive(Clone, Copy, PartialEq, Eq)]
enum PathKind {
    Partial,
    Final,
}

fn spawn_whisper_worker(
    jetstream: async_nats::jetstream::Context,
    mut rx: mpsc::Receiver<Job>,
    model: Arc<WhisperModel>,
    path: PathKind,
) {
    tokio::spawn(async move {
        while let Some(job) = rx.recv().await {
            let model = model.clone();
            let pcm = job.pcm_16k;
            let started = now_seconds();

            let result = tokio::task::spawn_blocking(move || model.transcribe(&pcm)).await;

            let text = match result {
                Ok(Ok(text)) => text,
                Ok(Err(err)) => {
                    error!("whisper inference error: {err:#}");
                    continue;
                }
                Err(err) => {
                    error!("whisper worker panicked: {err}");
                    continue;
                }
            };

            if text.trim().is_empty() {
                continue;
            }

            let elapsed_ms = (now_seconds() - started) * 1000.0;
            let publish = match path {
                PathKind::Partial => {
                    publish_partial(&jetstream, &text, &job.utterance_id).await
                }
                PathKind::Final => {
                    info!(text = %text, took_ms = elapsed_ms, "final transcript");
                    publish_final(&jetstream, &text, &job.utterance_id, job.latency, "whisper")
                        .await
                }
            };
            if let Err(err) = publish {
                error!("stt-agent failed to publish transcript: {err:#}");
            }
        }
    });
}

/// Mock workers keep the deterministic path available for CI without pulling
/// models, while still exercising the real buffering/endpointing pipeline.
fn spawn_mock_workers(
    jetstream: async_nats::jetstream::Context,
    mut partial_rx: mpsc::Receiver<Job>,
    mut final_rx: mpsc::Receiver<Job>,
    transcript: String,
) {
    let js = jetstream.clone();
    let text = transcript.clone();
    tokio::spawn(async move {
        while let Some(job) = partial_rx.recv().await {
            if let Err(err) = publish_partial(&js, &text, &job.utterance_id).await {
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

async fn publish_partial(
    jetstream: &async_nats::jetstream::Context,
    text: &str,
    utterance_id: &str,
) -> Result<()> {
    let mut metadata_map = JsonMap::new();
    metadata_map.insert("text".to_string(), json!(text));
    metadata_map.insert("is_partial".to_string(), json!(true));

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
        // Whisper does not classify emotion or paralinguistics. Left empty rather
        // than fabricated; populating these needs a model that actually predicts them.
        paralinguistic_events: Vec::new(),
        speculative_intent: speculative.clone(),
        metadata: metadata_map,
        timestamp: now_seconds(),
        utterance_id: Some(utterance_id.to_string()),
    };

    jetstream
        .publish(
            topics::AUDIO_PERCEPTION,
            Bytes::from(serde_json::to_vec(&perception)?),
        )
        .await?
        .await?;

    if let Some(spec) = speculative {
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
    partial_tx: &mpsc::Sender<Job>,
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
        jetstream
            .publish(
                topics::AMBIENT_NOISE_TELEMETRY,
                Bytes::from(serde_json::to_vec(&telemetry)?),
            )
            .await?
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
    jetstream
        .publish(
            topics::USER_VOICE_PROPERTIES,
            Bytes::from(serde_json::to_vec(&voice_properties)?),
        )
        .await?
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
        }
        VadEvent::SpeechContinues if !force_cut => {
            if now - guard.last_partial_at >= config.partial_interval_ms / 1000.0 {
                guard.last_partial_at = now;
                let pcm = guard.buffer.clone();
                let utt = guard.utterance_id.clone();
                let rate = source_rate;
                drop(guard);

                if let Ok(pcm_16k) = audio::resample_to_16k(&pcm, rate) {
                    // try_send: drop rather than queue if the fast model is busy.
                    let _ = partial_tx.try_send(Job {
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
    let keywords = [
        "stop", "wait", "hold", "no", "wrong", "quiet", "alex", "friend",
    ]
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
