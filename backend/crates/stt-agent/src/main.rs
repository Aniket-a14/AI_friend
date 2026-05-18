use anyhow::{Context, Result};
use async_nats::Message;
use bytes::Bytes;
use contracts::{
    topics, AudioPerception, AudioStop, ChatInput, ChatInputMetadata, JsonMap, LatencyHop,
    LatencyMetadata, SpeculativeIntent, HEADER_LATENCY_META,
};
use futures_util::StreamExt;
use serde_json::json;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{error, info, warn};
use uuid::Uuid;

#[derive(Debug, Clone)]
struct SttConfig {
    nats_url: String,
    target_sample_rate: u32,
    mock_transcript: Option<String>,
}

impl SttConfig {
    fn from_env() -> Self {
        Self {
            nats_url: env_or("NATS_URL", "nats://localhost:4222"),
            target_sample_rate: env_or("STT_TARGET_SAMPLE_RATE", "16000")
                .parse()
                .unwrap_or(16_000),
            mock_transcript: std::env::var("RUST_STT_MOCK_TRANSCRIPT")
                .ok()
                .filter(|s| !s.trim().is_empty()),
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

    let config = SttConfig::from_env();
    let client = async_nats::connect(config.nats_url.clone())
        .await
        .with_context(|| format!("connect to NATS at {}", config.nats_url))?;
    let jetstream = async_nats::jetstream::new(client.clone());
    let mut subscriber = client.subscribe(topics::AUDIO_INBOUND).await?;

    info!("rust stt-agent subscribed to {}", topics::AUDIO_INBOUND);

    while let Some(message) = subscriber.next().await {
        if let Err(err) = handle_audio_inbound(&config, &jetstream, message).await {
            error!("stt-agent failed to process audio.inbound: {err:#}");
        }
    }

    Ok(())
}

async fn handle_audio_inbound(
    config: &SttConfig,
    jetstream: &async_nats::jetstream::Context,
    message: Message,
) -> Result<()> {
    let metadata = metadata_from_headers(&message);
    let channels = metadata
        .as_ref()
        .and_then(|m| m.source.parse::<usize>().ok())
        .unwrap_or(1);
    let _pcm_16k_mono = normalize_pcm_i16(&message.payload, channels.max(1));

    let Some(text) = config
        .mock_transcript
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    else {
        warn!(
            "received PCM but no Rust STT model backend is configured; dropping without transcript"
        );
        return Ok(());
    };

    let utterance_id = Uuid::new_v4().to_string();
    let latency_metadata = append_latency(metadata, topics::CHAT_INPUT);
    let chat = ChatInput {
        text: text.to_string(),
        utterance_id: Some(utterance_id.clone()),
        turn_id: None,
        metadata: ChatInputMetadata {
            source: "whisper".to_string(),
            confidence: 0.9,
            utterance_id: Some(utterance_id.clone()),
        },
        latency_metadata: Some(latency_metadata),
    };

    jetstream
        .publish(topics::CHAT_INPUT, Bytes::from(serde_json::to_vec(&chat)?))
        .await?
        .await?;

    if let Some(speculative) = build_speculative_intent(text, &utterance_id) {
        let perception = build_audio_perception(text, &speculative);
        jetstream
            .publish(
                topics::AUDIO_PERCEPTION,
                Bytes::from(serde_json::to_vec(&perception)?),
            )
            .await?
            .await?;

        let stop = AudioStop {
            interrupt: true,
            speculative: true,
            reason: None,
            command_text: None,
            intent: Some(speculative.name.clone()),
            intent_type: "VOICE_INTERRUPTION".to_string(),
            keywords: speculative.keywords.clone(),
            confidence: speculative.confidence,
            perception_text: Some(speculative.text.clone()),
            utterance_id: speculative.utterance_id.clone(),
            turn_id: None,
        };
        jetstream
            .publish(topics::AUDIO_STOP, Bytes::from(serde_json::to_vec(&stop)?))
            .await?
            .await?;
    }

    let _ = config.target_sample_rate;
    Ok(())
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
    });
    metadata.hops.push(LatencyHop {
        agent: "stt_agent".to_string(),
        subject: subject.to_string(),
        timestamp: now,
    });
    metadata
}

fn normalize_pcm_i16(bytes: &[u8], channels: usize) -> Vec<i16> {
    let samples = bytes
        .chunks_exact(2)
        .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
        .collect::<Vec<_>>();

    if channels <= 1 {
        return samples;
    }

    samples
        .chunks_exact(channels)
        .map(|frame| {
            let total: i32 = frame.iter().map(|sample| *sample as i32).sum();
            (total / channels as i32) as i16
        })
        .collect()
}

fn build_speculative_intent(text: &str, utterance_id: &str) -> Option<SpeculativeIntent> {
    let lower = text.to_lowercase();
    let keywords = [
        "stop", "wait", "hold", "no", "wrong", "quiet", "alex", "friend",
    ]
    .iter()
    .filter(|keyword| {
        lower
            .split_whitespace()
            .any(|word| word.contains(**keyword))
    })
    .map(|keyword| keyword.to_string())
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
    fn rejects_json_style_audio_by_not_parsing_text_from_pcm() {
        let normalized = normalize_pcm_i16(br#"{"audio":"legacy-json"}"#, 1);
        assert!(!normalized.is_empty());
        assert!(build_speculative_intent("", "utt-1").is_none());
    }

    #[test]
    fn downmixes_multichannel_pcm_like_python_agent() {
        let stereo_samples = [1000_i16, -1000, 3000, 1000];
        let mut bytes = Vec::new();
        for sample in stereo_samples {
            bytes.extend_from_slice(&sample.to_le_bytes());
        }

        let mono = normalize_pcm_i16(&bytes, 2);
        assert_eq!(mono, vec![0, 2000]);
    }

    #[test]
    fn speculative_stop_shape_matches_current_contract() {
        let spec = build_speculative_intent("stop now", "utt-1").unwrap();
        let perception = build_audio_perception("stop now", &spec);

        assert_eq!(perception.intent.as_deref(), Some("SPECULATIVE_STOP"));
        assert_eq!(perception.intent_type, "COMMAND");
        assert_eq!(perception.keywords, vec!["stop", "no"]);
        assert_eq!(
            perception
                .speculative_intent
                .unwrap()
                .utterance_id
                .as_deref(),
            Some("utt-1")
        );
    }
}
