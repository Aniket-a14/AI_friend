use anyhow::{Context, Result};
use async_nats::HeaderMap;
use bytes::Bytes;
use contracts::{
    topics, vad_to_prosody, ChatOutput, HEADER_LATENCY_META, HEADER_PAYLOAD_FORMAT,
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
            nats_url: env_or("NATS_URL", "nats://localhost:4222"),
            sovits_url: env_or("SOVITS_URL", "http://localhost:9871"),
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

    info!("rust voice-agent subscribed to {}", topics::CHAT_OUTPUT);

    while let Some(message) = subscriber.next().await {
        match serde_json::from_slice::<ChatOutput>(&message.payload) {
            Ok(event) => {
                if let Err(err) = handle_chat_output(
                    &config,
                    &http,
                    &jetstream,
                    event,
                    last_distance.clone(),
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

async fn handle_chat_output(
    config: &VoiceConfig,
    http: &Client,
    jetstream: &async_nats::jetstream::Context,
    event: ChatOutput,
    last_distance: std::sync::Arc<std::sync::Mutex<f64>>,
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

    let prosody = vad_to_prosody(event.affect.as_ref());
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

    for part in split_temporal_parts(content)? {
        match part {
            TemporalPart::Silence(ms) => {
                let pcm = contracts::silence_pcm(ms, config.sample_rate);
                publish_pcm(jetstream, pcm, &event).await?;
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
                        publish_pcm(jetstream, pcm_bytes, &event).await?;
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
}

fn split_temporal_parts(text: &str) -> Result<Vec<TemporalPart>> {
    let re = Regex::new(r"(<pause=\d+ms>|<hesitate>)")?;
    let mut parts = Vec::new();
    let mut last = 0;

    for mat in re.find_iter(text) {
        if mat.start() > last {
            push_text(&mut parts, &text[last..mat.start()]);
        }
        let token = mat.as_str();
        if token == "<hesitate>" {
            parts.push(TemporalPart::Silence(350));
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

async fn publish_pcm(
    jetstream: &async_nats::jetstream::Context,
    pcm: Vec<u8>,
    event: &ChatOutput,
) -> Result<()> {
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
                TemporalPart::Silence(350),
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
}
