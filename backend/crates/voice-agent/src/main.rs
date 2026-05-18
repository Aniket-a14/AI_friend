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
    let http = Client::new();

    info!("rust voice-agent subscribed to {}", topics::CHAT_OUTPUT);

    while let Some(message) = subscriber.next().await {
        match serde_json::from_slice::<ChatOutput>(&message.payload) {
            Ok(event) => {
                if let Err(err) = handle_chat_output(&config, &http, &jetstream, event).await {
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
) -> Result<()> {
    if event.done {
        return Ok(());
    }

    let Some(content) = event
        .content
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    else {
        return Ok(());
    };

    let prosody = vad_to_prosody(event.affect.as_ref());
    for part in split_temporal_parts(content)? {
        match part {
            TemporalPart::Silence(ms) => {
                let pcm = contracts::silence_pcm(ms, config.sample_rate);
                publish_pcm(jetstream, pcm, &event).await?;
            }
            TemporalPart::Text(text) => {
                let chunks = synthesize_stream(
                    config,
                    http,
                    &text,
                    prosody.rate,
                    prosody.pitch,
                    prosody.volume,
                )
                .await?;
                for chunk in chunks {
                    if !chunk.is_empty() {
                        publish_pcm(jetstream, chunk, &event).await?;
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
            parts.push(TemporalPart::Silence(ms));
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
) -> Result<Vec<Vec<u8>>> {
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
    let mut response = http.post(url).json(&payload).send().await?;
    if !response.status().is_success() {
        anyhow::bail!("SoVITS returned HTTP {}", response.status());
    }

    let mut chunks = Vec::new();
    while let Some(chunk) = response.chunk().await? {
        chunks.push(chunk.to_vec());
    }
    Ok(chunks)
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
}
