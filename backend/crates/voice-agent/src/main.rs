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
) -> Result<()> {
    let noise_scale = if let Ok(guard) = noise_scale_factor.lock() {
        *guard
    } else {
        1.0
    };
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
                publish_pcm(jetstream, pcm, &event, noise_scale).await?;
            }
            TemporalPart::Vocalization(name) => {
                ola_filter.clear_history();
                let mut pcm = load_vocalization_pcm(&name, config.sample_rate);
                pcm = reverb_filter.process(&pcm, 0.1);

                let target_att = if let Ok(guard) = attenuation_factor.lock() { *guard } else { 1.0 };
                apply_attenuation(&mut pcm, &mut current_attenuation_val, target_att);
                let _ = generate_and_publish_visemes(jetstream, &pcm);

                publish_pcm(jetstream, pcm, &event, noise_scale).await?;
            }
            TemporalPart::Hesitation(ms) => {
                ola_filter.clear_history();
                let mut pcm = generate_hesitation_pcm(ms, config.sample_rate, prosody.pitch);
                pcm = reverb_filter.process(&pcm, 0.1);

                let target_att = if let Ok(guard) = attenuation_factor.lock() { *guard } else { 1.0 };
                apply_attenuation(&mut pcm, &mut current_attenuation_val, target_att);
                let _ = generate_and_publish_visemes(jetstream, &pcm);

                publish_pcm(jetstream, pcm, &event, noise_scale).await?;
            }
            TemporalPart::Text(text) => {
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
}
