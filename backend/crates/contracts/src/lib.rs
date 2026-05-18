use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub mod topics {
    pub const CHAT_INPUT: &str = "chat.input";
    pub const CHAT_OUTPUT: &str = "chat.output";
    pub const AUDIO_PERCEPTION: &str = "audio.perception";
    pub const AUDIO_STOP: &str = "audio.stop";
    pub const AUDIO_RESUME: &str = "audio.resume";
    pub const AUDIO_INBOUND: &str = "audio.inbound";
    pub const AUDIO_STREAM: &str = "audio.stream";
}

pub const HEADER_LATENCY_META: &str = "X-Latency-Meta";
pub const HEADER_PAYLOAD_FORMAT: &str = "X-Payload-Format";
pub const PAYLOAD_FORMAT_RAW_PCM: &str = "binary/raw-pcm";

pub type JsonMap = BTreeMap<String, serde_json::Value>;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LatencyHop {
    pub agent: String,
    pub subject: String,
    pub timestamp: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LatencyMetadata {
    pub start_time: f64,
    pub hops: Vec<LatencyHop>,
    pub source: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub channels: Option<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sample_rate: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChatInputMetadata {
    #[serde(default = "default_whisper_source")]
    pub source: String,
    #[serde(default = "default_confidence")]
    pub confidence: f64,
    #[serde(default)]
    pub utterance_id: Option<String>,
}

fn default_whisper_source() -> String {
    "whisper".to_string()
}

fn default_confidence() -> f64 {
    0.9
}

impl Default for ChatInputMetadata {
    fn default() -> Self {
        Self {
            source: default_whisper_source(),
            confidence: default_confidence(),
            utterance_id: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChatInput {
    pub text: String,
    #[serde(default)]
    pub utterance_id: Option<String>,
    #[serde(default)]
    pub turn_id: Option<String>,
    #[serde(default)]
    pub metadata: ChatInputMetadata,
    #[serde(default)]
    pub latency_metadata: Option<LatencyMetadata>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChatOutputAffect {
    #[serde(default)]
    pub valence: f64,
    #[serde(default = "default_half")]
    pub arousal: f64,
    #[serde(default = "default_half")]
    pub dominance: f64,
    #[serde(default = "default_half")]
    pub trust: f64,
    #[serde(default = "default_attachment")]
    pub attachment: f64,
    #[serde(default = "default_neutral")]
    pub emotion: String,
}

fn default_half() -> f64 {
    0.5
}

fn default_attachment() -> f64 {
    0.1
}

fn default_neutral() -> String {
    "neutral".to_string()
}

impl Default for ChatOutputAffect {
    fn default() -> Self {
        Self {
            valence: 0.0,
            arousal: 0.5,
            dominance: 0.5,
            trust: 0.5,
            attachment: 0.1,
            emotion: default_neutral(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChatOutput {
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub done: bool,
    #[serde(default)]
    pub turn_id: Option<String>,
    #[serde(default)]
    pub affect: Option<ChatOutputAffect>,
    #[serde(default = "default_one")]
    pub confidence: f64,
    #[serde(default)]
    pub intensity: f64,
    #[serde(default = "default_one")]
    pub speaking_rate: f64,
    #[serde(default)]
    pub pause_bias: f64,
    #[serde(default)]
    pub paralinguistic_tags: Vec<String>,
    #[serde(default)]
    pub timestamp: f64,
    #[serde(default)]
    pub full_response: Option<String>,
    #[serde(default)]
    pub generation_error: Option<String>,
    #[serde(default)]
    pub proactive: bool,
    #[serde(default)]
    pub latency_metadata: Option<LatencyMetadata>,
}

fn default_one() -> f64 {
    1.0
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SpeculativeIntent {
    #[serde(default = "default_speculative_stop")]
    pub name: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub confidence: f64,
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub timestamp: f64,
    #[serde(default)]
    pub utterance_id: Option<String>,
}

fn default_speculative_stop() -> String {
    "SPECULATIVE_STOP".to_string()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioPerception {
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub intent: Option<String>,
    #[serde(default = "default_conversational")]
    pub intent_type: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub confidence: f64,
    #[serde(default)]
    pub snr: f64,
    #[serde(default)]
    pub paralinguistic_events: Vec<String>,
    #[serde(default)]
    pub speculative_intent: Option<SpeculativeIntent>,
    #[serde(default)]
    pub metadata: JsonMap,
    #[serde(default)]
    pub timestamp: f64,
    #[serde(default)]
    pub utterance_id: Option<String>,
}

fn default_conversational() -> String {
    "CONVERSATIONAL".to_string()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioStop {
    #[serde(default = "default_true")]
    pub interrupt: bool,
    #[serde(default)]
    pub speculative: bool,
    #[serde(default)]
    pub reason: Option<String>,
    #[serde(default)]
    pub command_text: Option<String>,
    #[serde(default)]
    pub intent: Option<String>,
    #[serde(default = "default_voice_interruption")]
    pub intent_type: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub confidence: f64,
    #[serde(default)]
    pub perception_text: Option<String>,
    #[serde(default)]
    pub utterance_id: Option<String>,
    #[serde(default)]
    pub turn_id: Option<String>,
}

fn default_true() -> bool {
    true
}

fn default_voice_interruption() -> String {
    "VOICE_INTERRUPTION".to_string()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioResume {
    #[serde(default = "default_conflict_rejected")]
    pub reason: String,
    #[serde(default)]
    pub perception_text: Option<String>,
    #[serde(default)]
    pub utterance_id: Option<String>,
}

fn default_conflict_rejected() -> String {
    "conflict_rejected".to_string()
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Prosody {
    pub rate: f64,
    pub pitch: f64,
    pub volume: f64,
    pub pause_bias: f64,
}

pub fn vad_to_prosody(affect: Option<&ChatOutputAffect>) -> Prosody {
    let affect = affect.cloned().unwrap_or_default();
    let rate = 1.0 + (affect.arousal - 0.5);
    let pitch = 1.0 + (affect.arousal - 0.5) * 0.7 + affect.valence * 0.3;
    let volume = 0.4 + affect.dominance * 0.6;

    Prosody {
        rate: clamp_round(rate, 0.6, 1.8),
        pitch: clamp_round(pitch, 0.5, 2.0),
        volume: clamp_round(volume, 0.1, 1.0),
        pause_bias: 1.0 - affect.arousal,
    }
}

fn clamp_round(value: f64, min: f64, max: f64) -> f64 {
    let clamped = value.max(min).min(max);
    (clamped * 100.0).round() / 100.0
}

pub fn silence_pcm(ms: u32, sample_rate: u32) -> Vec<u8> {
    let samples = ((ms as u64).saturating_mul(sample_rate as u64) + 999) / 1000;
    let bytes = samples.saturating_mul(2);
    vec![0; bytes as usize]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chat_output_round_trips_current_contract_shape() {
        let fixture = include_str!("../fixtures/chat_output_chunk.json");
        let parsed: ChatOutput = serde_json::from_str(fixture).unwrap();

        assert_eq!(
            parsed.content.as_deref(),
            Some("Hey there<pause=20ms>friend")
        );
        assert_eq!(parsed.turn_id.as_deref(), Some("turn-1"));
        assert_eq!(parsed.affect.as_ref().unwrap().emotion, "happy");

        let serialized = serde_json::to_value(parsed).unwrap();
        let expected: serde_json::Value = serde_json::from_str(fixture).unwrap();
        assert_eq!(serialized, expected);
    }

    #[test]
    fn speculative_audio_stop_round_trips_current_contract_shape() {
        let fixture = include_str!("../fixtures/audio_stop_speculative.json");
        let parsed: AudioStop = serde_json::from_str(fixture).unwrap();

        assert!(parsed.interrupt);
        assert!(parsed.speculative);
        assert_eq!(parsed.intent.as_deref(), Some("SPECULATIVE_STOP"));

        let serialized = serde_json::to_value(parsed).unwrap();
        let expected: serde_json::Value = serde_json::from_str(fixture).unwrap();
        assert_eq!(serialized, expected);
    }

    #[test]
    fn silence_uses_configured_sample_rate() {
        assert_eq!(silence_pcm(10, 16_000).len(), 320);
        assert_eq!(silence_pcm(10, 32_000).len(), 640);
    }

    #[test]
    fn prosody_pitch_respects_negative_valence_range() {
        let negative = ChatOutputAffect {
            valence: -1.0,
            ..Default::default()
        };
        let positive = ChatOutputAffect {
            valence: 1.0,
            ..Default::default()
        };

        assert!(vad_to_prosody(Some(&negative)).pitch < vad_to_prosody(Some(&positive)).pitch);
    }
}
