use anyhow::{Context, Result};
use async_nats::HeaderMap;
use bytes::Bytes;
use contracts::{
    topics, vad_to_prosody, AmbientNoiseTelemetry, ChatOutput, PlaybackVisemes, HEADER_LATENCY_META, HEADER_PAYLOAD_FORMAT,
    PAYLOAD_FORMAT_RAW_PCM,
};
use futures_util::StreamExt;
use regex::Regex;
use reqwest::Client;
use serde_json::json;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{error, info, warn};
use std::collections::HashMap;
use std::path::Path;
use ort::session::Session;
use ort::value::Tensor;
use rubato::{
    Resampler, SincFixedIn, SincInterpolationParameters, SincInterpolationType, WindowFunction,
};

/// VITS flow / stochastic-duration noise scales.
///
/// These set baseline *variability*, not affect. The emotional controls are
/// `Prosody { rate, pitch, volume }`.
const VITS_NOISE_SCALE: f32 = 0.667;
const VITS_NOISE_SCALE_W: f32 = 0.8;

/// Graph interface of the sherpa-onnx VITS family (vits-ljs and friends).
///
/// This crate previously used piper's names (`input`, `input_lengths`, a fused
/// `scales` tensor, output `output`) while its `Phonemizer` required a
/// `lexicon.txt` that piper voices do not ship — the two halves targeted
/// different model families, so local synthesis could not have worked with
/// either. The lexicon side is load-bearing (there is no runtime phonemizer),
/// so the graph side was corrected to match it.
const VITS_INPUT_TOKENS: &str = "x";
const VITS_INPUT_TOKEN_LEN: &str = "x_length";
const VITS_INPUT_NOISE_SCALE: &str = "noise_scale";
const VITS_INPUT_LENGTH_SCALE: &str = "length_scale";
const VITS_INPUT_NOISE_SCALE_W: &str = "noise_scale_w";
const VITS_OUTPUT_AUDIO: &str = "y";

const VITS_REQUIRED_INPUTS: [&str; 5] = [
    VITS_INPUT_TOKENS,
    VITS_INPUT_TOKEN_LEN,
    VITS_INPUT_NOISE_SCALE,
    VITS_INPUT_LENGTH_SCALE,
    VITS_INPUT_NOISE_SCALE_W,
];

/// Blank token id interleaved between phonemes when the model sets `add_blank=1`.
const VITS_BLANK_ID: i64 = 0;

/// Mirrors the clamps `contracts::vad_to_prosody` already applies. Repeated here
/// because `dynamic_prosody` can be overridden from the mesh and must not be
/// trusted to be in range — a zero or negative rate would divide by zero below.
const MIN_RATE: f32 = 0.6;
const MAX_RATE: f32 = 1.8;
const MIN_PITCH: f32 = 0.5;
const MAX_PITCH: f32 = 2.0;

struct Phonemizer {
    lexicon: HashMap<String, Vec<String>>,
    tokens: HashMap<String, i64>,
}

impl Phonemizer {
    /// Load a lexicon-based phonemizer.
    ///
    /// Both files are **required**. The previous implementation wrapped each read
    /// in `if let Ok(..)` and returned `Ok` regardless, so a missing or
    /// unparseable file produced an empty table, `phonemize` returned only
    /// `[bos, eos]`, and the agent rendered silence with nothing logged anywhere.
    /// Failing here instead lets `load_local_engine` fall through to another
    /// candidate — or report honestly that local synthesis is unavailable.
    fn load(lexicon_path: &Path, tokens_path: &Path) -> Result<Self> {
        let lexicon_raw = std::fs::read_to_string(lexicon_path)
            .with_context(|| format!("read lexicon {}", lexicon_path.display()))?;
        let tokens_raw = std::fs::read_to_string(tokens_path)
            .with_context(|| format!("read tokens {}", tokens_path.display()))?;

        // sherpa-onnx lexicons are whitespace-separated: `word ph1 ph2 ...`.
        // This previously split on '\t' only and required >= 2 parts, so every
        // line of a space-separated lexicon collapsed to a single part and was
        // dropped — yielding an empty lexicon. `split_whitespace` accepts either.
        let mut lexicon = HashMap::new();
        for line in lexicon_raw.lines() {
            let mut parts = line.split_whitespace();
            let Some(word) = parts.next() else { continue };
            let phonemes: Vec<String> = parts.map(String::from).collect();
            if phonemes.is_empty() {
                continue;
            }
            lexicon.insert(word.to_lowercase(), phonemes);
        }

        let mut tokens = HashMap::new();
        for line in tokens_raw.lines() {
            // Token names may themselves be whitespace (e.g. the space phoneme),
            // so split off the trailing id rather than splitting the whole line.
            let Some((name, id)) = line.rsplit_once(' ') else { continue };
            if let Ok(id) = id.trim().parse::<i64>() {
                tokens.insert(name.to_string(), id);
            }
        }

        if lexicon.is_empty() {
            anyhow::bail!(
                "lexicon {} parsed to zero entries — wrong format or wrong model \
                 (a lexicon-based VITS voice is required, not an espeak/piper one)",
                lexicon_path.display()
            );
        }
        if tokens.is_empty() {
            anyhow::bail!(
                "tokens {} parsed to zero entries",
                tokens_path.display()
            );
        }

        info!(
            lexicon_entries = lexicon.len(),
            token_entries = tokens.len(),
            "phonemizer loaded"
        );
        Ok(Self { lexicon, tokens })
    }

    /// Map text to VITS token ids via the lexicon.
    ///
    /// The model declares `add_blank=1`, so phonemes are interleaved with the
    /// blank token in the canonical VITS form `[0, p1, 0, p2, 0, ..., pn, 0]`.
    /// The previous code emitted `[p1, 0, p2, 0, ...]` — missing the leading
    /// blank — and bracketed with piper's `^`/`$` tokens, which the sherpa-onnx
    /// VITS vocabulary does not define (so they silently never appended).
    fn phonemize(&self, text: &str) -> Vec<i64> {
        let mut phoneme_ids = Vec::new();
        for word in text.split_whitespace() {
            let clean_word: String = word
                .chars()
                .filter(|c| c.is_alphanumeric())
                .collect::<String>()
                .to_lowercase();
            let Some(phonemes) = self.lexicon.get(&clean_word) else {
                continue;
            };
            for p in phonemes {
                if let Some(&id) = self.tokens.get(p) {
                    phoneme_ids.push(id);
                }
            }
        }

        if phoneme_ids.is_empty() {
            return Vec::new();
        }

        let mut ids = Vec::with_capacity(phoneme_ids.len() * 2 + 1);
        ids.push(VITS_BLANK_ID);
        for id in phoneme_ids {
            ids.push(id);
            ids.push(VITS_BLANK_ID);
        }
        ids
    }
}

struct LocalTtsEngine {
    session: std::sync::Mutex<Session>,
    phonemizer: Phonemizer,
    /// Rate the model actually renders at (read from ONNX metadata).
    native_sample_rate: u32,
    /// Rate the mesh expects; output is resampled to this.
    target_sample_rate: u32,
}

impl LocalTtsEngine {
    fn load(
        model_path: &Path,
        lexicon_path: &Path,
        tokens_path: &Path,
        target_sample_rate: u32,
    ) -> Result<Self> {
        let mut builder = Session::builder()?
            .with_execution_providers([
                ort::ep::TensorRT::default().build(),
                ort::ep::CUDA::default().build(),
                ort::ep::CoreML::default().build(),
            ])
            .map_err(|e| anyhow::anyhow!("failed to configure execution providers: {:?}", e))?;

        let session = builder.commit_from_file(model_path)?;

        // Verify the graph interface at load rather than discovering it as
        // "Invalid input name" on the first utterance.
        let actual: Vec<&str> = session.inputs().iter().map(|i| i.name()).collect();
        if let Some(missing) = VITS_REQUIRED_INPUTS
            .iter()
            .find(|name| !actual.contains(name))
        {
            anyhow::bail!(
                "model {} does not expose input `{missing}` (actual inputs: {actual:?}). \
                 This build targets the sherpa-onnx VITS family (vits-ljs); espeak/piper \
                 voices use `input`/`input_lengths`/`scales` and ship no lexicon.txt.",
                model_path.display()
            );
        }

        let phonemizer = Phonemizer::load(lexicon_path, tokens_path)?;
        let native_sample_rate = model_sample_rate(&session, target_sample_rate);

        if native_sample_rate != target_sample_rate {
            info!(
                native_sample_rate,
                target_sample_rate, "model rate differs from mesh rate; output will be resampled"
            );
        }

        Ok(Self {
            session: std::sync::Mutex::new(session),
            phonemizer,
            native_sample_rate,
            target_sample_rate,
        })
    }

    /// Render `text` under the full prosody triple.
    ///
    /// Previously only `rate` reached the vocoder: `pitch` and `volume` were
    /// computed by the cognitive layer and then discarded, so every affective
    /// state collapsed onto "how fast the agent talks". All three now apply.
    fn synthesize(&self, text: &str, rate: f32, pitch: f32, volume: f32) -> Result<Vec<u8>> {
        let ids = self.phonemizer.phonemize(text);
        if ids.is_empty() {
            return Ok(Vec::new());
        }

        let num_phonemes = ids.len();
        let rate = rate.clamp(MIN_RATE, MAX_RATE);
        let pitch = pitch.clamp(MIN_PITCH, MAX_PITCH);

        // VITS exposes no pitch input, so pitch is applied by resampling the
        // rendered waveform below. That also divides duration by `pitch`, so
        // pre-multiply length_scale by `pitch` to cancel it and let the final
        // duration honour `rate` alone.
        //
        // Resampling shifts formants along with F0, so extreme shifts sound
        // "chipmunk"/"Darth Vader". Acceptable only because `vad_to_prosody`
        // squashes pitch through `tanh`, keeping realistic values near 0.85..1.20.
        // A wider expressive range needs a formant-preserving shifter (PSOLA/WORLD).
        let length_scale = pitch / rate;

        let inputs = ort::inputs![
            VITS_INPUT_TOKENS => Tensor::from_array(
                ndarray::Array2::from_shape_vec((1, num_phonemes), ids)?
            )?,
            VITS_INPUT_TOKEN_LEN => Tensor::from_array(
                ndarray::Array1::from_vec(vec![num_phonemes as i64])
            )?,
            // Separate scalars, not one fused `scales` tensor.
            VITS_INPUT_NOISE_SCALE => Tensor::from_array(
                ndarray::Array1::from_vec(vec![VITS_NOISE_SCALE])
            )?,
            VITS_INPUT_LENGTH_SCALE => Tensor::from_array(
                ndarray::Array1::from_vec(vec![length_scale])
            )?,
            VITS_INPUT_NOISE_SCALE_W => Tensor::from_array(
                ndarray::Array1::from_vec(vec![VITS_NOISE_SCALE_W])
            )?,
        ];

        // Copy the waveform out and release the session lock before resampling:
        // the shift is CPU-bound and must not serialise other synthesis calls.
        let audio: Vec<f32> = {
            let mut session_guard = self
                .session
                .lock()
                .map_err(|e| anyhow::anyhow!("mutex poisoned: {e}"))?;
            let outputs = session_guard.run(inputs)?;
            let output_value = outputs
                .get(VITS_OUTPUT_AUDIO)
                .with_context(|| format!("missing output audio tensor `{VITS_OUTPUT_AUDIO}`"))?;
            let (_dimensions, audio_data) = output_value.try_extract_tensor::<f32>()?;
            audio_data.to_vec()
        };

        // One sinc pass does both jobs; two would double the cost and compound
        // interpolation error.
        //
        //   pitch shift      : 1 / pitch          (see the length_scale note above)
        //   rate conversion  : target / native    (model rate -> mesh rate)
        //
        // Duration still resolves to `1/rate` in seconds:
        //   generated = pitch/rate  ->  x (target/native)/pitch  ->  /target
        //     = base/(rate * native)  seconds
        let ratio =
            (self.target_sample_rate as f64 / self.native_sample_rate as f64) / pitch as f64;
        let audio = resample_by(&audio, ratio)?;

        // Volume is applied in the f32 domain, before quantisation, so a quiet
        // agent does not pay an extra rounding penalty. `Prosody.volume` is an
        // absolute level in 0.1..=1.0 (1.0 = full scale), not a gain around 1.0.
        let volume = volume.clamp(0.0, 1.0);
        let mut pcm_bytes = Vec::with_capacity(audio.len() * 2);
        for &sample in &audio {
            let scaled = sample * volume * i16::MAX as f32;
            let clamped = scaled.clamp(i16::MIN as f32, i16::MAX as f32) as i16;
            pcm_bytes.extend_from_slice(&clamped.to_le_bytes());
        }

        Ok(pcm_bytes)
    }
}

/// Resolve the local TTS engine, preferring custom weights over the base voice.
///
/// Falls through to the next candidate when a model is missing **or unloadable**.
/// The previous implementation branched on `custom.exists()` and swallowed the
/// load error with `.ok()`, so a present-but-broken custom model disabled local
/// synthesis outright rather than falling back to base — the exact opposite of the
/// "seamless fallback / robust startup" guarantee in `docs/ARCHITECTURE.md`. A
/// corrupt or placeholder `custom_vits.onnx` was therefore strictly worse than
/// having no custom model at all, and said nothing about why.
fn load_local_engine(target_sample_rate: u32) -> Option<LocalTtsEngine> {
    let candidates = [
        (
            "CUSTOM",
            Path::new("models/custom/custom_vits.onnx"),
            Path::new("models/custom/lexicon.txt"),
            Path::new("models/custom/tokens.txt"),
        ),
        (
            "BASE",
            Path::new("models/base/model.onnx"),
            Path::new("models/base/lexicon.txt"),
            Path::new("models/base/tokens.txt"),
        ),
    ];

    for (label, model, lexicon, tokens) in candidates {
        if !model.exists() {
            continue;
        }
        info!(model = %model.display(), "Loading {label} local voice weights...");
        match LocalTtsEngine::load(model, lexicon, tokens, target_sample_rate) {
            Ok(engine) => {
                info!("Loaded {label} local voice weights.");
                return Some(engine);
            }
            Err(e) => warn!(
                model = %model.display(),
                "Failed to load {label} voice weights: {e:#}. Falling through to next candidate."
            ),
        }
    }

    warn!("No usable local voice weights. Local ONNX engine offline; synthesis will use the remote endpoint.");
    None
}

/// Band-limited resample: `output.len() ~= samples.len() * ratio`.
///
/// Serves two fused purposes in `synthesize` (see there): pitch shifting and
/// native-rate -> mesh-rate conversion.
fn resample_by(samples: &[f32], ratio: f64) -> Result<Vec<f32>> {
    if samples.is_empty() || (ratio - 1.0).abs() < 1e-6 {
        return Ok(samples.to_vec());
    }
    if !ratio.is_finite() || ratio <= 0.0 {
        anyhow::bail!("invalid resample ratio {ratio}");
    }

    let params = SincInterpolationParameters {
        sinc_len: 128,
        f_cutoff: 0.95,
        interpolation: SincInterpolationType::Linear,
        oversampling_factor: 128,
        window: WindowFunction::BlackmanHarris2,
    };

    let mut resampler = SincFixedIn::<f32>::new(ratio, 2.0, params, samples.len(), 1)
        .context("construct resampler")?;

    let output = resampler
        .process(&[samples.to_vec()], None)
        .context("resample")?;

    Ok(output.into_iter().next().unwrap_or_default())
}

/// Native output rate of a sherpa-onnx VITS model, from its ONNX metadata.
///
/// Falls back to `default_rate` when absent. Publishing a model's audio at the
/// wrong rate is an inaudible-in-code but glaring runtime bug: a 22.05 kHz voice
/// emitted into a 32 kHz stream plays ~45% fast and sharp.
fn model_sample_rate(session: &Session, default_rate: u32) -> u32 {
    // `metadata()` -> Result, `custom()` -> Option<String> (ort 2.0.0-rc.12).
    match session
        .metadata()
        .ok()
        .and_then(|m| m.custom("sample_rate"))
        .and_then(|v| v.trim().parse::<u32>().ok())
    {
        Some(rate) if rate > 0 => rate,
        _ => {
            warn!(
                default_rate,
                "model exposes no usable `sample_rate` metadata; assuming default"
            );
            default_rate
        }
    }
}

#[derive(Debug, Clone, serde::Deserialize)]
struct VisionDescriptionMsg {
    user_distance: Option<f64>,
    #[allow(dead_code)]
    description: Option<String>,
    #[allow(dead_code)]
    source: Option<String>,
}

struct ReverbFilter {
    buffer: Vec<f32>,
    index: usize,
    gain: f32,
    pending_byte: Option<u8>,
}

impl ReverbFilter {
    fn new(delay_samples: usize, gain: f32) -> Self {
        Self {
            buffer: vec![0.0; delay_samples],
            index: 0,
            gain,
            pending_byte: None,
        }
    }

    fn process(&mut self, bytes: &[u8], wet_gain: f32) -> Vec<u8> {
        let mut framed =
            Vec::with_capacity(bytes.len() + if self.pending_byte.is_some() { 1 } else { 0 });
        if let Some(byte) = self.pending_byte.take() {
            framed.push(byte);
        }
        framed.extend_from_slice(bytes);
        if framed.len() % 2 != 0 {
            self.pending_byte = framed.pop();
        }

        let mut samples = framed
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        for sample in samples.iter_mut() {
            let input = *sample as f32;
            let delayed = self.buffer[self.index];
            let output = input + self.gain * delayed;
            self.buffer[self.index] = output;
            self.index = (self.index + 1) % self.buffer.len();

            let blended = (1.0 - wet_gain) * input + wet_gain * output;
            *sample = blended.clamp(i16::MIN as f32, i16::MAX as f32) as i16;
        }

        let mut output_bytes = Vec::with_capacity(samples.len() * 2);
        for sample in samples {
            output_bytes.extend_from_slice(&sample.to_le_bytes());
        }
        output_bytes
    }
}

struct OlaCrossfadeFilter {
    sample_rate: u32,
    last_prosody: Option<contracts::Prosody>,
    last_samples: Vec<i16>,
    active_fade_buffer: Vec<i16>,
    fade_in_progress: bool,
    fade_index: usize,
    pending_byte: Option<u8>,
}

impl OlaCrossfadeFilter {
    fn new(sample_rate: u32) -> Self {
        Self {
            sample_rate,
            last_prosody: None,
            last_samples: Vec::new(),
            active_fade_buffer: Vec::new(),
            fade_in_progress: false,
            fade_index: 0,
            pending_byte: None,
        }
    }

    fn clear_history(&mut self) {
        self.last_samples.clear();
        self.active_fade_buffer.clear();
        self.fade_in_progress = false;
        self.fade_index = 0;
    }

    fn notify_new_prosody(&mut self, prosody: contracts::Prosody) {
        let is_shift = match self.last_prosody {
            None => false,
            Some(last) => last != prosody,
        };
        self.last_prosody = Some(prosody);

        if is_shift {
            if !self.last_samples.is_empty() {
                self.active_fade_buffer = self.last_samples.clone();
                self.fade_in_progress = true;
                self.fade_index = 0;
                info!("Prosody shift detected! Initiating 15ms OLA crossfade.");
            }
        }
    }

    fn process(&mut self, bytes: &[u8]) -> Vec<u8> {
        let n = (self.sample_rate * 15 / 1000) as usize;

        let mut framed = Vec::with_capacity(bytes.len() + if self.pending_byte.is_some() { 1 } else { 0 });
        if let Some(byte) = self.pending_byte.take() {
            framed.push(byte);
        }
        framed.extend_from_slice(bytes);
        if framed.len() % 2 != 0 {
            self.pending_byte = framed.pop();
        }

        let mut samples = framed
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        if samples.is_empty() {
            return Vec::new();
        }

        if self.fade_in_progress && !self.active_fade_buffer.is_empty() {
            let fade_len = self.active_fade_buffer.len().min(n);
            for s in samples.iter_mut() {
                if self.fade_index < fade_len {
                    let prev_s = self.active_fade_buffer[self.fade_index] as f32;
                    let curr_s = *s as f32;
                    let t = self.fade_index as f32 / fade_len as f32;
                    let blended = (1.0 - t) * prev_s + t * curr_s;
                    *s = blended.clamp(i16::MIN as f32, i16::MAX as f32) as i16;
                    self.fade_index += 1;
                } else {
                    self.fade_in_progress = false;
                    break;
                }
            }
        }

        // Maintain rolling buffer of last n samples
        if samples.len() >= n {
            self.last_samples = samples[samples.len() - n..].to_vec();
        } else {
            self.last_samples.extend_from_slice(&samples);
            if self.last_samples.len() > n {
                let excess = self.last_samples.len() - n;
                self.last_samples.drain(0..excess);
            }
        }

        let mut output_bytes = Vec::with_capacity(samples.len() * 2);
        for sample in samples {
            output_bytes.extend_from_slice(&sample.to_le_bytes());
        }
        output_bytes
    }
}

#[derive(Debug, Clone)]
struct VoiceConfig {
    nats_url: String,
    sovits_url: String,
    ref_audio_path: String,
    ref_text: String,
    tts_language: String,
    sample_rate: u32,
}

impl VoiceConfig {
    fn from_env() -> Self {
        Self {
            nats_url: env_or("NATS_URL", "nats://127.0.0.1:4222"),
            sovits_url: env_or("SOVITS_URL", "http://127.0.0.1:9871"),
            ref_audio_path: env_or("REF_AUDIO_PATH", "output/sample_en_gold.wav"),
            ref_text: env_or(
                "REF_TEXT",
                "At the end of the exam, the program shows the performance summary.",
            ),
            tts_language: env_or("TTS_LANGUAGE", "en"),
            sample_rate: env_or("SAMPLE_RATE", "32000").parse().unwrap_or(32_000),
        }
    }
}

fn env_or(name: &str, fallback: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| fallback.to_string())
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let config = VoiceConfig::from_env();
    let client = async_nats::connect(config.nats_url.clone())
        .await
        .with_context(|| format!("connect to NATS at {}", config.nats_url))?;
    let jetstream = async_nats::jetstream::new(client.clone());
    let mut subscriber = client.subscribe(topics::CHAT_OUTPUT).await?;
    let http = Client::builder()
        .connect_timeout(std::time::Duration::from_secs(3))
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .context("build reqwest client with timeouts")?;

    let local_engine = load_local_engine(config.sample_rate);

    let local_engine = std::sync::Arc::new(local_engine);

    let last_distance = std::sync::Arc::new(std::sync::Mutex::new(1.0));
    let noise_scale_factor = std::sync::Arc::new(std::sync::Mutex::new(1.0f64));
    let noise_floor_moving_avg = std::sync::Arc::new(std::sync::Mutex::new(0.01f64));

    // Subscribe to ambient noise telemetry and track noise floor dynamically
    let noise_scale_clone = noise_scale_factor.clone();
    let noise_avg_clone = noise_floor_moving_avg.clone();
    let mut noise_sub = client.subscribe(topics::AMBIENT_NOISE_TELEMETRY).await?;
    tokio::spawn(async move {
        while let Some(msg) = noise_sub.next().await {
            if let Ok(telemetry) = serde_json::from_slice::<AmbientNoiseTelemetry>(&msg.payload) {
                if let Ok(mut avg_guard) = noise_avg_clone.lock() {
                    *avg_guard = *avg_guard * 0.8 + telemetry.rms_energy * 0.2;
                    let avg = *avg_guard;
                    let scale = if avg < 0.01 {
                        0.7 + (avg / 0.01) * 0.3
                    } else {
                        let excess = (avg - 0.01) / 0.02;
                        1.0 + (excess * 0.5).min(0.5)
                    };
                    if let Ok(mut scale_guard) = noise_scale_clone.lock() {
                        *scale_guard = scale;
                    }
                }
            }
        }
    });

    // Subscribe to vision description and track user distance dynamically
    let last_distance_clone = last_distance.clone();
    let mut vision_sub = client.subscribe(topics::VISION_DESCRIPTION).await?;
    tokio::spawn(async move {
        while let Some(msg) = vision_sub.next().await {
            match serde_json::from_slice::<VisionDescriptionMsg>(&msg.payload) {
                Ok(desc) => {
                    if let Some(dist) = desc.user_distance {
                        if let Ok(mut guard) = last_distance_clone.lock() {
                            *guard = dist;
                        }
                    }
                }
                Err(err) => {
                    warn!(
                        "Failed to deserialize vision description message: {:?}",
                        err
                    );
                }
            }
        }
        warn!("Vision description subscription stream closed.");
    });

    // Abort flag for immediate voice playback stop
    let abort_flag = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let attenuation_factor = std::sync::Arc::new(std::sync::Mutex::new(1.0f64));
    let dynamic_prosody = std::sync::Arc::new(std::sync::Mutex::new(None::<contracts::Prosody>));

    // Subscribe to audio.stop and set abort flag or duck volume (attenuate)
    let abort_flag_stop = abort_flag.clone();
    let attenuation_stop = attenuation_factor.clone();
    let mut stop_sub = client.subscribe(topics::AUDIO_STOP).await?;
    tokio::spawn(async move {
        while let Some(msg) = stop_sub.next().await {
            match serde_json::from_slice::<contracts::AudioStop>(&msg.payload) {
                Ok(stop) => {
                    if stop.speculative {
                        info!("Received SPECULATIVE AUDIO_STOP - ducking current voice playback.");
                        if let Ok(mut guard) = attenuation_stop.lock() {
                            *guard = 0.30;
                        }
                    } else {
                        info!("Received CONFIRMED AUDIO_STOP - aborting current voice playback.");
                        abort_flag_stop.store(true, std::sync::atomic::Ordering::SeqCst);
                    }
                }
                Err(_) => {
                    info!("Received generic AUDIO_STOP - aborting current voice playback.");
                    abort_flag_stop.store(true, std::sync::atomic::Ordering::SeqCst);
                }
            }
        }
    });

    // Subscribe to audio.resume and restore volume (attenuation_factor = 1.0)
    let attenuation_resume = attenuation_factor.clone();
    let mut resume_sub = client.subscribe(topics::AUDIO_RESUME).await?;
    tokio::spawn(async move {
        while let Some(_msg) = resume_sub.next().await {
            info!("Received AUDIO_RESUME - restoring voice playback volume.");
            if let Ok(mut guard) = attenuation_resume.lock() {
                *guard = 1.0;
            }
        }
    });

    // Subscribe to agent.voice.modulation and update dynamic prosody overrides
    let dynamic_prosody_clone = dynamic_prosody.clone();
    let mut modulation_sub = client.subscribe(topics::AGENT_VOICE_MODULATION).await?;
    tokio::spawn(async move {
        while let Some(msg) = modulation_sub.next().await {
            if let Ok(mod_payload) = serde_json::from_slice::<contracts::AgentVoiceModulation>(&msg.payload) {
                if !mod_payload.trajectory.is_empty() {
                    let steady_frames: Vec<&contracts::ProsodyFrame> = mod_payload.trajectory.iter()
                        .filter(|f| f.time_offset_ms >= 200 && f.time_offset_ms <= 2700)
                        .collect();

                    let target_frames = if !steady_frames.is_empty() {
                        steady_frames
                    } else {
                        mod_payload.trajectory.iter().collect()
                    };

                    let count = target_frames.len() as f64;
                    let sum_rate: f64 = target_frames.iter().map(|f| f.rate).sum();
                    let sum_pitch: f64 = target_frames.iter().map(|f| f.pitch).sum();
                    let sum_volume: f64 = target_frames.iter().map(|f| f.volume).sum();

                    let rep_rate = sum_rate / count;
                    let rep_pitch = sum_pitch / count;
                    let rep_volume = sum_volume / count;

                    info!("Received AGENT_VOICE_MODULATION (steady-state): rate={:.2}, pitch={:.2}, volume={:.2}", rep_rate, rep_pitch, rep_volume);
                    if let Ok(mut guard) = dynamic_prosody_clone.lock() {
                        *guard = Some(contracts::Prosody {
                            rate: rep_rate,
                            pitch: rep_pitch,
                            volume: rep_volume,
                            pause_bias: 1.0,
                        });
                    }
                }
            }
        }
    });


    info!("rust voice-agent subscribed to {}", topics::CHAT_OUTPUT);

    let mut ola_filter = OlaCrossfadeFilter::new(config.sample_rate);
    let mut last_turn_id: Option<String> = None;

    while let Some(message) = subscriber.next().await {
        match serde_json::from_slice::<ChatOutput>(&message.payload) {
            Ok(event) => {
                if event.done {
                    // End of current stream; safe point to clear interruption state.
                    abort_flag.store(false, std::sync::atomic::Ordering::SeqCst);
                    if let Ok(mut guard) = attenuation_factor.lock() {
                        *guard = 1.0;
                    }
                    last_turn_id = None;
                    continue;
                }

                // Detect start of a new stream/response by tracking turn_id changes
                if let Some(ref current_turn_id) = event.turn_id {
                    let is_new_stream = match last_turn_id {
                        Some(ref prev_id) => prev_id != current_turn_id,
                        None => true,
                    };
                    if is_new_stream {
                        last_turn_id = Some(current_turn_id.clone());
                        abort_flag.store(false, std::sync::atomic::Ordering::SeqCst);
                        if let Ok(mut guard) = attenuation_factor.lock() {
                            *guard = 1.0;
                        }
                    }
                }

                if abort_flag.load(std::sync::atomic::Ordering::SeqCst) {
                    // Drop trailing chunks after interruption until stream completion.
                    continue;
                }
                if let Err(err) = handle_chat_output(
                    &config,
                    &http,
                    &jetstream,
                    event,
                    last_distance.clone(),
                    &mut ola_filter,
                    abort_flag.clone(),
                    attenuation_factor.clone(),
                    dynamic_prosody.clone(),
                    noise_scale_factor.clone(),
                    local_engine.clone(),
                )
                .await
                {
                    error!("voice-agent failed to process chat.output: {err:#}");
                }
            }
            Err(err) => warn!("dropping invalid chat.output payload: {err}"),
        }
    }

    Ok(())
}

fn load_vocalization_pcm(name: &str, sample_rate: u32) -> Vec<u8> {
    let paths = [
        format!("output/{}.wav", name),
        format!("assets/{}.wav", name),
        format!("{}.wav", name),
    ];
    for path in &paths {
        if let Ok(data) = std::fs::read(path) {
            if let Some(pcm) = extract_wav_data(&data) {
                info!("Successfully loaded vocalization {} from {}", name, path);
                return pcm;
            } else {
                warn!("WAV file at {} found, but missing data chunk or invalid format.", path);
            }
        }
    }
    warn!("Vocalization file not found: {}. Generating synthetic fallback.", name);
    let num_samples = (sample_rate as f32 * 0.5) as usize;
    let mut pcm = Vec::with_capacity(num_samples * 2);
    for i in 0..num_samples {
        let val = (((i * 1103515245 + 12345) / 65536) % 2001) as i32 - 1000;
        pcm.extend_from_slice(&(val as i16).to_le_bytes());
    }
    pcm
}

fn extract_wav_data(data: &[u8]) -> Option<Vec<u8>> {
    // Minimal RIFF/WAV parser: find "data" chunk and return its contents
    if data.len() < 12 || &data[0..4] != b"RIFF" || &data[8..12] != b"WAVE" {
        return None;
    }
    let mut pos = 12;
    while pos + 8 <= data.len() {
        let chunk_id = &data[pos..pos + 4];
        let chunk_size = u32::from_le_bytes([
            data[pos + 4],
            data[pos + 5],
            data[pos + 6],
            data[pos + 7],
        ]) as usize;
        if chunk_id == b"data" {
            let start = pos + 8;
            let end = (start + chunk_size).min(data.len());
            return Some(data[start..end].to_vec());
        }
        pos += 8 + chunk_size;
        if chunk_size % 2 != 0 {
            pos += 1; // RIFF chunks are word-aligned
        }
    }
    None
}

fn generate_hesitation_pcm(duration_ms: u32, sample_rate: u32, pitch: f64) -> Vec<u8> {
    let num_samples = (sample_rate as f64 * (duration_ms as f64 / 1000.0)) as usize;
    let mut pcm = Vec::with_capacity(num_samples * 2);
    let f0 = 150.0 * pitch;
    let omega = 2.0 * std::f64::consts::PI * f0 / (sample_rate as f64);

    for i in 0..num_samples {
        let sine = (omega * i as f64).sin() * 300.0;
        let noise = (((i * 1103515245 + 12345) / 65536) % 201) as f64 - 100.0;
        let val = (sine + noise) as i16;
        pcm.extend_from_slice(&val.to_le_bytes());
    }
    pcm
}

fn apply_attenuation(pcm: &mut [u8], current_val: &mut f64, target_val: f64) {
    if pcm.len() < 2 {
        return;
    }
    let mut samples = pcm
        .chunks_exact(2)
        .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
        .collect::<Vec<i16>>();

    let num_samples = samples.len();
    let step = (target_val - *current_val) / num_samples as f64;

    for sample in samples.iter_mut() {
        *current_val += step;
        let val = *sample as f64 * (*current_val);
        *sample = val.clamp(i16::MIN as f64, i16::MAX as f64) as i16;
    }

    *current_val = target_val; // Ensure we land exactly at target

    let mut idx = 0;
    for s in samples {
        let bytes = s.to_le_bytes();
        pcm[idx] = bytes[0];
        pcm[idx + 1] = bytes[1];
        idx += 2;
    }
}

fn generate_and_publish_visemes(
    jetstream: &async_nats::jetstream::Context,
    pcm: &[u8],
) -> Result<()> {
    if pcm.is_empty() {
        return Ok(());
    }
    let samples = pcm
        .chunks_exact(2)
        .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
        .collect::<Vec<i16>>();
    let num_samples = samples.len();
    if num_samples == 0 {
        return Ok(());
    }
    let sum_sq: f64 = samples.iter()
        .map(|&s| {
            let norm = s as f64 / i16::MAX as f64;
            norm * norm
        })
        .sum();
    let rms = (sum_sq / num_samples as f64).sqrt();
    let target_level = (rms * 10.0).min(1.0); // scale up for visualization

    let viseme_id = if target_level < 0.05 {
        "sil".to_string()
    } else if target_level < 0.3 {
        "AA".to_string()
    } else if target_level < 0.6 {
        "O".to_string()
    } else {
        "AH".to_string()
    };

    let viseme = PlaybackVisemes {
        target_level,
        viseme_id,
        timestamp: now_seconds(),
    };

    let jetstream = jetstream.clone();
    tokio::spawn(async move {
        let _ = jetstream.publish(
            topics::AUDIO_PLAYBACK_VISEMES,
            Bytes::from(serde_json::to_vec(&viseme).unwrap()),
        ).await;
    });

    Ok(())
}

async fn handle_chat_output(
    config: &VoiceConfig,
    http: &Client,
    jetstream: &async_nats::jetstream::Context,
    event: ChatOutput,
    last_distance: std::sync::Arc<std::sync::Mutex<f64>>,
    ola_filter: &mut OlaCrossfadeFilter,
    abort_flag: std::sync::Arc<std::sync::atomic::AtomicBool>,
    attenuation_factor: std::sync::Arc<std::sync::Mutex<f64>>,
    dynamic_prosody: std::sync::Arc<std::sync::Mutex<Option<contracts::Prosody>>>,
    noise_scale_factor: std::sync::Arc<std::sync::Mutex<f64>>,
    local_engine: std::sync::Arc<Option<LocalTtsEngine>>,
) -> Result<()> {
    if event.done {
        return Ok(());
    }

    let mut reverb_filter = ReverbFilter::new(
        (config.sample_rate as f32 * 0.05) as usize, // 50ms delay
        0.5,
    );

    let Some(content) = event
        .content
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    else {
        return Ok(());
    };

    let prosody = if let Ok(guard) = dynamic_prosody.lock() {
        guard.clone().unwrap_or_else(|| vad_to_prosody(event.affect.as_ref()))
    } else {
        vad_to_prosody(event.affect.as_ref())
    };
    ola_filter.notify_new_prosody(prosody);

    let distance = event
        .affect
        .as_ref()
        .and_then(|a| a.user_distance)
        .unwrap_or_else(|| {
            if let Ok(guard) = last_distance.lock() {
                *guard
            } else {
                1.0
            }
        });

    let mut current_attenuation_val = 1.0f64;

    for part in split_temporal_parts(content)? {
        if abort_flag.load(std::sync::atomic::Ordering::SeqCst) {
            info!("Aborting playback due to AUDIO_STOP event.");
            break;
        }
        match part {
            TemporalPart::Silence(ms) => {
                ola_filter.clear_history();
                let pcm = contracts::silence_pcm(ms, config.sample_rate);
                if let Ok(guard) = attenuation_factor.lock() {
                    current_attenuation_val = *guard;
                }
                let noise_scale = if let Ok(guard) = noise_scale_factor.lock() {
                    *guard
                } else {
                    1.0
                };
                publish_pcm(jetstream, pcm, &event, noise_scale).await?;
            }
            TemporalPart::Vocalization(name) => {
                ola_filter.clear_history();
                let mut pcm = load_vocalization_pcm(&name, config.sample_rate);
                pcm = reverb_filter.process(&pcm, 0.1);

                let target_att = if let Ok(guard) = attenuation_factor.lock() { *guard } else { 1.0 };
                apply_attenuation(&mut pcm, &mut current_attenuation_val, target_att);
                let _ = generate_and_publish_visemes(jetstream, &pcm);

                let gain = utterance_gain(&noise_scale_factor, prosody.volume);
                publish_pcm(jetstream, pcm, &event, gain).await?;
            }
            TemporalPart::Hesitation(ms) => {
                ola_filter.clear_history();
                let mut pcm = generate_hesitation_pcm(ms, config.sample_rate, prosody.pitch);
                pcm = reverb_filter.process(&pcm, 0.1);

                let target_att = if let Ok(guard) = attenuation_factor.lock() { *guard } else { 1.0 };
                apply_attenuation(&mut pcm, &mut current_attenuation_val, target_att);
                let _ = generate_and_publish_visemes(jetstream, &pcm);

                let gain = utterance_gain(&noise_scale_factor, prosody.volume);
                publish_pcm(jetstream, pcm, &event, gain).await?;
            }
            TemporalPart::Text(text) => {
                if let Some(engine) = local_engine.as_ref() {
                    // Local engine bakes `volume` into the waveform, so publish_pcm
                    // below applies only the ambient-noise compensation. (The remote
                    // path differs — see the `else` branch.)
                    match engine.synthesize(
                        &text,
                        prosody.rate as f32,
                        prosody.pitch as f32,
                        prosody.volume as f32,
                    ) {
                        Ok(pcm_bytes) => {
                            for chunk in pcm_bytes.chunks(4096) {
                                if abort_flag.load(std::sync::atomic::Ordering::SeqCst) {
                                    info!("Aborting playback due to AUDIO_STOP event.");
                                    break;
                                }
                                let mut chunk_vec = chunk.to_vec();

                                const REVERB_DRY_LIMIT: f64 = 2.5;
                                const REVERB_WET_LIMIT: f64 = 3.5;
                                let wet_gain = if distance <= REVERB_DRY_LIMIT {
                                    0.0
                                } else if distance >= REVERB_WET_LIMIT {
                                    1.0
                                } else {
                                    ((distance - REVERB_DRY_LIMIT) / (REVERB_WET_LIMIT - REVERB_DRY_LIMIT))
                                        as f32
                                };

                                chunk_vec = reverb_filter.process(&chunk_vec, wet_gain);
                                chunk_vec = ola_filter.process(&chunk_vec);

                                let target_att = if let Ok(guard) = attenuation_factor.lock() { *guard } else { 1.0 };
                                apply_attenuation(&mut chunk_vec, &mut current_attenuation_val, target_att);
                                let _ = generate_and_publish_visemes(jetstream, &chunk_vec);

                                let noise_scale = if let Ok(guard) = noise_scale_factor.lock() { *guard } else { 1.0 };
                                publish_pcm(jetstream, chunk_vec, &event, noise_scale).await?;
                            }
                        }
                        Err(e) => {
                            error!("Local ONNX synthesis failed: {:?}", e);
                        }
                    }
                } else {
                    let mut response = synthesize_stream(
                        config,
                        http,
                        &text,
                        prosody.rate,
                        prosody.pitch,
                        prosody.volume,
                    )
                    .await?;
                    while let Some(chunk) = response.chunk().await? {
                        if abort_flag.load(std::sync::atomic::Ordering::SeqCst) {
                            info!("Aborting synthesis chunk stream due to AUDIO_STOP event.");
                            break;
                        }
                        if !chunk.is_empty() {
                            let mut pcm_bytes = chunk.to_vec();

                            // Ambient compensation only: `synthesize_stream` already
                            // sent rate/pitch/volume to the remote engine, so folding
                            // `prosody.volume` in here would apply it twice.
                            let noise_scale = if let Ok(guard) = noise_scale_factor.lock() {
                                *guard
                            } else {
                                1.0
                            };

                            const REVERB_DRY_LIMIT: f64 = 2.5;
                            const REVERB_WET_LIMIT: f64 = 3.5;
                            let wet_gain = if distance <= REVERB_DRY_LIMIT {
                                0.0
                            } else if distance >= REVERB_WET_LIMIT {
                                1.0
                            } else {
                                ((distance - REVERB_DRY_LIMIT) / (REVERB_WET_LIMIT - REVERB_DRY_LIMIT))
                                    as f32
                            };

                            pcm_bytes = reverb_filter.process(&pcm_bytes, wet_gain);
                            pcm_bytes = ola_filter.process(&pcm_bytes);

                            let target_att = if let Ok(guard) = attenuation_factor.lock() { *guard } else { 1.0 };
                            apply_attenuation(&mut pcm_bytes, &mut current_attenuation_val, target_att);
                            let _ = generate_and_publish_visemes(jetstream, &pcm_bytes);

                            publish_pcm(jetstream, pcm_bytes, &event, noise_scale).await?;
                        }
                    }
                }
            }
        }
    }

    Ok(())
}

#[derive(Debug, PartialEq)]
enum TemporalPart {
    Text(String),
    Silence(u32),
    Vocalization(String),
    Hesitation(u32),
}

fn split_temporal_parts(text: &str) -> Result<Vec<TemporalPart>> {
    let re = Regex::new(r"(<pause=\d+ms>|<hesitate>|<breath_fast>|<sigh_soft>)")?;
    let mut parts = Vec::new();
    let mut last = 0;

    for mat in re.find_iter(text) {
        if mat.start() > last {
            push_text(&mut parts, &text[last..mat.start()]);
        }
        let token = mat.as_str();
        if token == "<hesitate>" {
            parts.push(TemporalPart::Hesitation(350));
        } else if token == "<breath_fast>" {
            parts.push(TemporalPart::Vocalization("breath_fast".to_string()));
        } else if token == "<sigh_soft>" {
            parts.push(TemporalPart::Vocalization("sigh_soft".to_string()));
        } else {
            let ms = token
                .trim_start_matches("<pause=")
                .trim_end_matches("ms>")
                .parse::<u32>()
                .context("parse pause duration")?;
            let clamped_ms = ms.min(5000);
            parts.push(TemporalPart::Silence(clamped_ms));
        }
        last = mat.end();
    }

    if last < text.len() {
        push_text(&mut parts, &text[last..]);
    }

    Ok(parts)
}

fn push_text(parts: &mut Vec<TemporalPart>, text: &str) {
    let text = text.trim();
    if !text.is_empty() {
        parts.push(TemporalPart::Text(text.to_string()));
    }
}

async fn synthesize_stream(
    config: &VoiceConfig,
    http: &Client,
    text: &str,
    speed: f64,
    pitch: f64,
    volume: f64,
) -> Result<reqwest::Response> {
    let payload = json!({
        "text": text,
        "text_lang": config.tts_language,
        "ref_audio_path": config.ref_audio_path,
        "prompt_text": config.ref_text,
        "prompt_lang": config.tts_language,
        "text_split_method": "cut5",
        "batch_size": 1,
        "media_type": "raw",
        "streaming_mode": 1,
        "speed_factor": speed,
        "pitch": pitch,
        "volume": volume,
    });

    let url = format!("{}/tts", config.sovits_url.trim_end_matches('/'));
    let response = http.post(url).json(&payload).send().await?;
    if !response.status().is_success() {
        anyhow::bail!("SoVITS returned HTTP {}", response.status());
    }

    Ok(response)
}

/// Publish gain for locally-generated PCM that has *not* already had
/// `Prosody.volume` baked in (vocalisations, hesitations): emotional level x
/// ambient-noise compensation.
///
/// Without this, a quiet agent's "hmm" would play at full level next to its
/// attenuated words, breaking the illusion mid-utterance.
fn utterance_gain(noise_scale_factor: &std::sync::Mutex<f64>, volume: f64) -> f64 {
    let noise_scale = noise_scale_factor.lock().map(|g| *g).unwrap_or(1.0);
    volume * noise_scale
}

fn scale_pcm_in_place(pcm: &mut [u8], noise_scale: f64) {
    if noise_scale != 1.0 && pcm.len() >= 2 {
        let mut samples = pcm
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        for sample in samples.iter_mut() {
            let val = *sample as f64 * noise_scale;
            *sample = val.clamp(i16::MIN as f64, i16::MAX as f64) as i16;
        }

        let mut idx = 0;
        for s in samples {
            let bytes = s.to_le_bytes();
            pcm[idx] = bytes[0];
            pcm[idx + 1] = bytes[1];
            idx += 2;
        }
    }
}

async fn publish_pcm(
    jetstream: &async_nats::jetstream::Context,
    mut pcm: Vec<u8>,
    event: &ChatOutput,
    noise_scale: f64,
) -> Result<()> {
    scale_pcm_in_place(&mut pcm, noise_scale);

    let mut headers = HeaderMap::new();
    headers.insert(HEADER_PAYLOAD_FORMAT, PAYLOAD_FORMAT_RAW_PCM);
    headers.insert(
        HEADER_LATENCY_META,
        build_latency_metadata(event).to_string(),
    );

    jetstream
        .publish_with_headers(topics::AUDIO_STREAM, headers, Bytes::from(pcm))
        .await?
        .await?;
    Ok(())
}

fn build_latency_metadata(event: &ChatOutput) -> serde_json::Value {
    let now = now_seconds();
    let mut meta = event
        .latency_metadata
        .as_ref()
        .map(serde_json::to_value)
        .and_then(Result::ok)
        .unwrap_or_else(|| json!({"start_time": now, "hops": [], "source": "voice_agent"}));

    if let Some(obj) = meta.as_object_mut() {
        obj.entry("start_time").or_insert(json!(now));
        obj.entry("source").or_insert(json!("voice_agent"));
        let hops = obj.entry("hops").or_insert(json!([]));
        if let Some(hops) = hops.as_array_mut() {
            hops.push(json!({
                "agent": "voice_agent",
                "subject": topics::AUDIO_STREAM,
                "timestamp": now,
            }));
        }
    }

    meta
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
    fn timing_tags_become_silence_parts_not_text() {
        let parts = split_temporal_parts("hello<pause=20ms>there<hesitate>").unwrap();
        assert_eq!(
            parts,
            vec![
                TemporalPart::Text("hello".to_string()),
                TemporalPart::Silence(20),
                TemporalPart::Text("there".to_string()),
                TemporalPart::Hesitation(350),
            ]
        );
    }

    #[test]
    fn latency_metadata_appends_voice_hop() {
        let event: ChatOutput = serde_json::from_str(include_str!(
            "../../contracts/fixtures/chat_output_chunk.json"
        ))
        .unwrap();
        let meta = build_latency_metadata(&event);
        let hops = meta["hops"].as_array().unwrap();

        assert_eq!(hops.last().unwrap()["agent"], "voice_agent");
        assert_eq!(hops.last().unwrap()["subject"], topics::AUDIO_STREAM);
    }

    #[test]
    fn test_reverb_filter_processing() {
        let mut filter = ReverbFilter::new(4, 0.5);
        let input_pcm = vec![10, 0, 20, 0, 30, 0, 40, 0, 50, 0, 60, 0];

        // 100% wet output
        let processed = filter.process(&input_pcm, 1.0);

        // Since delay is 4 samples (8 bytes), and gain is 0.5:
        // The first 4 samples should be unchanged (except buffer updates)
        assert_eq!(processed.len(), input_pcm.len());
        let out_samples = processed
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        // Sample 4 (5th sample, index 4): input 50, delayed sample 0 (index 0) * 0.5 = 10 * 0.5 = 5. Output: 50 + 5 = 55
        assert_eq!(out_samples[0], 10);
        assert_eq!(out_samples[4], 55);

        // Test 0% wet (completely dry output, but state still advances)
        let mut filter2 = ReverbFilter::new(4, 0.5);
        let processed2 = filter2.process(&input_pcm, 0.0);
        assert_eq!(processed2, input_pcm); // Exactly matches input
    }

    #[test]
    fn reverb_filter_preserves_samples_across_odd_chunks() {
        let mut filter = ReverbFilter::new(4, 0.5);

        let first = filter.process(&[10, 0, 20], 1.0);
        assert_eq!(first.len(), 2);
        assert_eq!(first, vec![10, 0]);

        let second = filter.process(&[0, 30, 0], 1.0);
        assert_eq!(second.len(), 4);
        let out_samples = second
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();
        assert_eq!(out_samples, vec![20, 30]);
    }

    #[test]
    fn test_ola_crossfade_filter() {
        let mut filter = OlaCrossfadeFilter::new(32_000); // 480 samples for 15ms

        // Initial state, no shift
        let p1 = contracts::Prosody {
            rate: 1.0,
            pitch: 1.0,
            volume: 1.0,
            pause_bias: 0.5,
        };
        filter.notify_new_prosody(p1);

        let chunk1 = vec![100_i16; 600]; // 600 samples
        let mut chunk1_bytes = Vec::new();
        for &s in &chunk1 {
            chunk1_bytes.extend_from_slice(&s.to_le_bytes());
        }

        let out1 = filter.process(&chunk1_bytes);
        assert_eq!(out1, chunk1_bytes); // Since there is no shift, it should be untouched

        // Let's check that rolling buffer is updated. The rolling buffer should contain the last 480 samples (all 100).
        assert_eq!(filter.last_samples.len(), 480);
        assert!(filter.last_samples.iter().all(|&s| s == 100));

        // Shift prosody!
        let p2 = contracts::Prosody {
            rate: 1.2,
            pitch: 1.1,
            volume: 0.8,
            pause_bias: 0.4,
        };
        filter.notify_new_prosody(p2);
        assert!(filter.fade_in_progress);

        // Process new chunk with different values, say 200_i16
        let chunk2 = vec![200_i16; 600];
        let mut chunk2_bytes = Vec::new();
        for &s in &chunk2 {
            chunk2_bytes.extend_from_slice(&s.to_le_bytes());
        }

        let out2_bytes = filter.process(&chunk2_bytes);
        let out2_samples = out2_bytes
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        // First sample should be exactly equal to previous sample (100) because t=0
        assert_eq!(out2_samples[0], 100);

        // As index progresses, the value should blend towards 200.
        // At index 240 (halfway through 480 samples of crossfade): it should be around (100 + 200) / 2 = 150.
        assert!((out2_samples[240] - 150).abs() <= 2);

        // At index 480, the crossfade has ended, so it should be exactly 200.
        assert_eq!(out2_samples[480], 200);

        // Fade in progress should now be false
        assert!(!filter.fade_in_progress);
    }

    #[test]
    fn test_vocal_gain_scaling() {
        // Test that noise scaling correctly shifts sample amplitudes
        let input_pcm = vec![1000_i16, -2000, 3000];
        let mut bytes = Vec::new();
        for &s in &input_pcm {
            bytes.extend_from_slice(&s.to_le_bytes());
        }

        // Test scaling down (quiet environment, multiplier < 1.0)
        let mut scale_down_bytes = bytes.clone();
        scale_pcm_in_place(&mut scale_down_bytes, 0.7);

        let scaled_down_samples = scale_down_bytes
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        assert_eq!(scaled_down_samples[0], 700);
        assert_eq!(scaled_down_samples[1], -1400);
        assert_eq!(scaled_down_samples[2], 2100);

        // Test scaling up (noisy environment, multiplier > 1.0)
        let mut scale_up_bytes = bytes.clone();
        scale_pcm_in_place(&mut scale_up_bytes, 1.4);

        let scaled_up_samples = scale_up_bytes
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<i16>>();

        assert_eq!(scaled_up_samples[0], 1400);
        assert_eq!(scaled_up_samples[1], -2800);
        assert_eq!(scaled_up_samples[2], 4200);
    }

    fn tone(len: usize, amp: f32) -> Vec<f32> {
        (0..len).map(|i| amp * (i as f32 * 0.10).sin()).collect()
    }

    #[test]
    fn resample_is_identity_at_unity_ratio() {
        let input = tone(512, 0.5);
        assert_eq!(resample_by(&input, 1.0).unwrap(), input);
    }

    #[test]
    fn resample_rejects_nonsense_ratios() {
        assert!(resample_by(&tone(64, 0.5), 0.0).is_err());
        assert!(resample_by(&tone(64, 0.5), -1.0).is_err());
        assert!(resample_by(&tone(64, 0.5), f64::NAN).is_err());
    }

    #[test]
    fn resample_scales_sample_count_by_ratio() {
        for &ratio in &[0.8f64, 1.25, 1.451] {
            let out = resample_by(&tone(4000, 0.5), ratio).unwrap();
            let expected = 4000.0 * ratio;
            assert!(
                (out.len() as f64 - expected).abs() / expected < 0.05,
                "ratio={ratio}: expected ~{expected}, got {}",
                out.len()
            );
        }
    }

    #[test]
    fn resample_handles_empty_input() {
        assert!(resample_by(&[], 1.5).unwrap().is_empty());
    }

    /// The invariant `synthesize` depends on: generating at length_scale
    /// `pitch/rate` and then resampling by `(target/native)/pitch` must leave the
    /// output *duration in seconds* a function of `rate` alone — independent of
    /// both pitch and the model's native rate.
    #[test]
    fn duration_depends_on_rate_alone_across_pitch_and_sample_rate() {
        const BASE_NATIVE_SAMPLES: f64 = 8000.0;
        for &(native, target) in &[(22_050u32, 32_000u32), (16_000, 32_000), (32_000, 32_000)] {
            for &(rate, pitch) in &[(1.0f64, 1.0f64), (1.0, 1.25), (1.4, 0.8), (0.7, 1.5)] {
                let length_scale = pitch / rate;
                let generated = (BASE_NATIVE_SAMPLES * length_scale).round() as usize;

                let ratio = (target as f64 / native as f64) / pitch;
                let out = resample_by(&tone(generated, 0.5), ratio).unwrap();

                let duration_s = out.len() as f64 / target as f64;
                let expected_s = (BASE_NATIVE_SAMPLES / native as f64) / rate;
                assert!(
                    (duration_s - expected_s).abs() / expected_s < 0.05,
                    "native={native} target={target} rate={rate} pitch={pitch}:                      expected ~{expected_s:.4}s, got {duration_s:.4}s"
                );
            }
        }
    }

    #[test]
    fn utterance_gain_combines_volume_and_noise() {
        let noise = std::sync::Mutex::new(1.2f64);
        assert!((utterance_gain(&noise, 0.5) - 0.6).abs() < 1e-9);
    }

    #[test]
    fn utterance_gain_falls_back_when_lock_poisoned() {
        let noise = std::sync::Arc::new(std::sync::Mutex::new(1.2f64));
        let n2 = noise.clone();
        let _ = std::thread::spawn(move || {
            let _g = n2.lock().unwrap();
            panic!("poison");
        })
        .join();
        // Poisoned lock must degrade to unity noise compensation, not silence.
        assert!((utterance_gain(&noise, 0.5) - 0.5).abs() < 1e-9);
    }

    #[test]
    fn placeholder_onnx_file_errors_instead_of_loading() {
        // The exact bytes the old exporter wrote under a *.onnx name. This must
        // surface as a recoverable Err so load_local_engine() can fall through to
        // the base voice; the old `.ok()` turned this into None and took local
        // synthesis down with it.
        let dir = std::env::temp_dir().join(format!("va-placeholder-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let model = dir.join("custom_vits.onnx");
        std::fs::write(&model, b"MOCK_CUSTOM_VITS_ONNX_CONTENT").unwrap();

        let result = LocalTtsEngine::load(
            &model,
            &dir.join("lexicon.txt"),
            &dir.join("tokens.txt"),
            32_000,
        );

        let _ = std::fs::remove_dir_all(&dir);
        assert!(
            result.is_err(),
            "a placeholder text file must not load as an ONNX model"
        );
    }

    /// Path to the provisioned base voice, relative to the crate root (cargo sets
    /// CWD there for tests). Populated by `scripts/research/export_models.py`.
    fn base_voice_dir() -> Option<std::path::PathBuf> {
        let dir = std::path::PathBuf::from("../../../models/base");
        dir.join("model.onnx").exists().then_some(dir)
    }

    fn load_base_voice() -> Option<LocalTtsEngine> {
        let dir = base_voice_dir()?;
        Some(
            LocalTtsEngine::load(
                &dir.join("model.onnx"),
                &dir.join("lexicon.txt"),
                &dir.join("tokens.txt"),
                32_000,
            )
            .expect("base voice is present but failed to load"),
        )
    }

    fn peak(pcm: &[u8]) -> i32 {
        pcm.chunks_exact(2)
            .map(|c| (i16::from_le_bytes([c[0], c[1]]) as i32).abs())
            .max()
            .unwrap_or(0)
    }

    const PHRASE: &str = "hello world this is a test of the voice";

    #[test]
    fn real_voice_phonemizes_words_not_just_bos_eos() {
        let Some(engine) = load_base_voice() else {
            eprintln!("SKIP: models/base not provisioned");
            return;
        };
        // The regression this guards: a mis-parsed lexicon yields an empty table,
        // so phonemize() returns only [bos, eos] and VITS renders silence.
        let ids = engine.phonemizer.phonemize(PHRASE);
        assert!(
            ids.len() > 20,
            "expected real phoneme ids for {PHRASE:?}, got only {} — lexicon likely empty",
            ids.len()
        );
    }

    #[test]
    fn real_voice_renders_audible_audio() {
        let Some(engine) = load_base_voice() else {
            eprintln!("SKIP: models/base not provisioned");
            return;
        };
        let pcm = engine.synthesize(PHRASE, 1.0, 1.0, 1.0).unwrap();
        assert!(pcm.len() > 2 * 8_000, "expected >0.25s of audio, got {} bytes", pcm.len());
        assert!(peak(&pcm) > 1_000, "audio is effectively silent (peak {})", peak(&pcm));
    }

    #[test]
    fn real_voice_duration_tracks_rate_and_ignores_pitch() {
        let Some(engine) = load_base_voice() else {
            eprintln!("SKIP: models/base not provisioned");
            return;
        };
        let normal = engine.synthesize(PHRASE, 1.0, 1.0, 1.0).unwrap().len() as f64;
        let high = engine.synthesize(PHRASE, 1.0, 1.3, 1.0).unwrap().len() as f64;
        let fast = engine.synthesize(PHRASE, 1.5, 1.0, 1.0).unwrap().len() as f64;

        // Pitch must not change duration -- the whole point of the length_scale
        // compensation. VITS' stochastic duration predictor adds run-to-run
        // variance, hence the loose bound.
        assert!(
            (high - normal).abs() / normal < 0.20,
            "pitch changed duration: normal={normal} high-pitch={high}"
        );
        // Rate must: 1.5x faster => ~2/3 the samples.
        let expected_fast = normal / 1.5;
        assert!(
            (fast - expected_fast).abs() / expected_fast < 0.20,
            "rate did not drive duration: expected ~{expected_fast}, got {fast}"
        );
    }

    #[test]
    fn real_voice_volume_scales_amplitude() {
        let Some(engine) = load_base_voice() else {
            eprintln!("SKIP: models/base not provisioned");
            return;
        };
        let loud = peak(&engine.synthesize(PHRASE, 1.0, 1.0, 1.0).unwrap()) as f64;
        let quiet = peak(&engine.synthesize(PHRASE, 1.0, 1.0, 0.5).unwrap()) as f64;
        assert!(loud > 0.0);
        let ratio = quiet / loud;
        assert!(
            (ratio - 0.5).abs() < 0.12,
            "volume 0.5 should halve peak amplitude; ratio was {ratio:.3}"
        );
    }

    #[test]
    fn real_voice_native_rate_is_resampled_to_mesh_rate() {
        let Some(engine) = load_base_voice() else {
            eprintln!("SKIP: models/base not provisioned");
            return;
        };
        eprintln!(
            "native={} target={}",
            engine.native_sample_rate, engine.target_sample_rate
        );
        assert_eq!(engine.target_sample_rate, 32_000);
        assert!(engine.native_sample_rate > 0);
    }

    fn wav_bytes(pcm: &[u8], sample_rate: u32) -> Vec<u8> {
        let mut w = Vec::new();
        let data_len = pcm.len() as u32;
        w.extend_from_slice(b"RIFF");
        w.extend_from_slice(&(36 + data_len).to_le_bytes());
        w.extend_from_slice(b"WAVEfmt ");
        w.extend_from_slice(&16u32.to_le_bytes()); // fmt chunk size
        w.extend_from_slice(&1u16.to_le_bytes()); // PCM
        w.extend_from_slice(&1u16.to_le_bytes()); // mono
        w.extend_from_slice(&sample_rate.to_le_bytes());
        w.extend_from_slice(&(sample_rate * 2).to_le_bytes()); // byte rate
        w.extend_from_slice(&2u16.to_le_bytes()); // block align
        w.extend_from_slice(&16u16.to_le_bytes()); // bits
        w.extend_from_slice(b"data");
        w.extend_from_slice(&data_len.to_le_bytes());
        w.extend_from_slice(pcm);
        w
    }

    /// Renders WAVs for human listening. Opt-in:
    ///   cargo test -p voice-agent render_prosody_demo_wavs -- --ignored --nocapture
    #[test]
    #[ignore]
    fn render_prosody_demo_wavs() {
        let engine = load_base_voice().expect("models/base must be provisioned");
        let out = std::path::PathBuf::from("../../../voice_demo");
        std::fs::create_dir_all(&out).unwrap();

        let phrase = "hello my friend it is really good to hear from you today";
        let cases: &[(&str, f32, f32, f32)] = &[
            ("neutral", 1.0, 1.0, 1.0),
            ("excited_fast_high", 1.4, 1.25, 1.0),
            ("sad_slow_low", 0.75, 0.85, 0.6),
            ("quiet_half_volume", 1.0, 1.0, 0.5),
            ("pitch_only_high", 1.0, 1.3, 1.0),
            ("rate_only_fast", 1.5, 1.0, 1.0),
        ];

        for (name, rate, pitch, volume) in cases {
            let pcm = engine.synthesize(phrase, *rate, *pitch, *volume).unwrap();
            let secs = pcm.len() as f64 / 2.0 / engine.target_sample_rate as f64;
            let path = out.join(format!("{name}.wav"));
            std::fs::write(&path, wav_bytes(&pcm, engine.target_sample_rate)).unwrap();
            eprintln!(
                "{name:20} rate={rate:.2} pitch={pitch:.2} vol={volume:.2} -> {secs:.2}s peak={} {}",
                peak(&pcm),
                path.display()
            );
        }
    }
}
