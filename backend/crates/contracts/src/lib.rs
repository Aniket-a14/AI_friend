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
    pub const VISION_DESCRIPTION: &str = "vision.description";
    pub const USER_VOICE_PROPERTIES: &str = "user.voice.properties";
    pub const AGENT_VOICE_MODULATION: &str = "agent.voice.modulation";
    pub const AUDIO_PLAYBACK_VISEMES: &str = "audio.playback.visemes";
    pub const AUDIO_PLAYBACK_PROGRESS: &str = "audio.playback.progress";
    pub const AMBIENT_NOISE_TELEMETRY: &str = "ambient.noise.telemetry";
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
    pub channels: Option<u64>,
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
    #[serde(default)]
    pub fatigue: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_distance: Option<f64>,
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
            fatigue: 0.0,
            user_distance: None,
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
    // The deprecated prosody block (confidence, intensity, speaking_rate,
    // pause_bias, paralinguistic_tags) was removed. Prosody has one source:
    // `vad_to_prosody` derives it from `affect` above. Nothing read these, and
    // the Python side populated them with a different formula.
    //
    // Removal is safe both ways round: this struct has no
    // `deny_unknown_fields`, so a message from an older producer still
    // carrying them deserializes and they are ignored. Note that
    // `contracts::Prosody` has its own `pause_bias` -- a different type, not
    // affected by this.
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct UserVoiceProperties {
    pub pitch_f0: f64,
    pub energy_rms: f64,
    pub tempo_wpm: f64,
    pub timestamp: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProsodyFrame {
    pub time_offset_ms: u32,
    pub rate: f64,
    pub pitch: f64,
    pub volume: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentVoiceModulation {
    pub trajectory: Vec<ProsodyFrame>,
    pub timestamp: f64,
}


#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PlaybackVisemes {
    pub target_level: f64,
    pub viseme_id: String,
    pub timestamp: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioPlaybackProgress {
    pub utterance_id: String,
    pub character_offset: u64,
    pub word_index: u64,
    pub completed: bool,
    pub timestamp: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AmbientNoiseTelemetry {
    pub rms_energy: f64,
    pub noise_floor_db: f64,
    pub timestamp: f64,
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

    // Fatigue dynamically slows down the rate and reduces pitch
    let fatigue_slow = 0.25 * affect.fatigue;
    let fatigue_pitch_drop = 0.1 * affect.fatigue;

    // Distance adaptation
    let user_distance = affect.user_distance.unwrap_or(1.0);
    let (dist_vol_mod, dist_pitch_mod) = if user_distance < 0.6 {
        (-0.15, -0.05) // close range (whisper)
    } else if user_distance > 1.5 {
        (0.2, 0.1) // far range (loud/calling out)
    } else {
        (0.0, 0.0) // baseline
    };

    // Continuous formulas from CVS-3.5 Roadmap
    // Sr = 1.0 + tanh(0.20 * arousal - 0.10 * valence - fatigue_slow)
    let rate_input = (0.20 * affect.arousal) - (0.10 * affect.valence) - fatigue_slow;
    let rate = 1.0 + rate_input.tanh();

    // Pm = 1.0 + tanh(0.05 * valence + 0.15 * arousal - 0.10 * dominance - fatigue_pitch_drop + dist_pitch_mod)
    let pitch_input = (0.05 * affect.valence) + (0.15 * affect.arousal) - (0.10 * affect.dominance) - fatigue_pitch_drop
        + dist_pitch_mod;
    let pitch = 1.0 + pitch_input.tanh();

    let volume = 0.4 + affect.dominance * 0.6 + dist_vol_mod;

    let v = 1.0 - affect.arousal;
    let pause_bias = v.clamp(0.0, 1.0);

    Prosody {
        rate: clamp_round(rate, 0.6, 1.8),
        pitch: clamp_round(pitch, 0.5, 2.0),
        volume: clamp_round(volume, 0.1, 1.0),
        pause_bias,
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

    #[test]
    fn prosody_responds_to_fatigue() {
        let fresh = ChatOutputAffect {
            fatigue: 0.0,
            ..Default::default()
        };
        let tired = ChatOutputAffect {
            fatigue: 0.8,
            ..Default::default()
        };

        let fresh_prosody = vad_to_prosody(Some(&fresh));
        let tired_prosody = vad_to_prosody(Some(&tired));

        assert!(tired_prosody.rate < fresh_prosody.rate);
        assert!(tired_prosody.pitch < fresh_prosody.pitch);
    }

    #[test]
    fn prosody_adapts_to_user_distance() {
        let close = ChatOutputAffect {
            user_distance: Some(0.4),
            ..Default::default()
        };
        let far = ChatOutputAffect {
            user_distance: Some(2.0),
            ..Default::default()
        };

        let close_prosody = vad_to_prosody(Some(&close));
        let far_prosody = vad_to_prosody(Some(&far));

        assert!(close_prosody.volume < far_prosody.volume);
        assert!(close_prosody.pitch < far_prosody.pitch);
    }
}
