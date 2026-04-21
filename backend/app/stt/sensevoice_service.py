import logging
import re
import numpy as np
import sherpa_onnx
from typing import Optional
from pathlib import Path

logger = logging.getLogger("sensevoice_service")

class SenseVoiceSTTService:
    """
    Ultra-low latency STT & Emotional Perception Service.
    Powered by SenseVoiceSmall (Non-autoregressive) on CPU/INT8.
    """

    def __init__(self, model_dir: str = "models/sensevoice"):
        self.model_dir = model_dir
        self.recognizer = None
        self.emotion_pattern = re.compile(r"<\|(HAPPY|SAD|ANGRY|NEUTRAL|FEARFUL|DISGUSTED|SURPRISED)\|>")
        self.event_pattern = re.compile(r"<\|(BGM|Speech|Applause|Laughter|Cry|Sneeze|Breath|Cough)\|>")
        
        # Mapping for Damped Bias State Machine
        self.emotion_map = {
            "HAPPY": 0.4,
            "SAD": -0.35,
            "ANGRY": -0.6,
            "NEUTRAL": 0.0,
            "FEARFUL": -0.4,
            "DISGUSTED": -0.5,
            "SURPRISED": 0.2
        }

    def load_model(self):
        """Initialize sherpa-onnx OfflineRecognizer."""
        base_path = Path(__file__).parent.parent.parent / self.model_dir
        
        # SenseVoiceSmall specific files
        model_path = base_path / "model.int8.onnx"
        tokens_path = base_path / "tokens.txt"
        
        if not model_path.exists() or not tokens_path.exists():
            logger.error(f"❌ SenseVoice models not found at {base_path}. Please run provisioning script.")
            return False

        try:
            # CPU/INT8 Configuration
            feat_config = sherpa_onnx.FeatureExtractorConfig(
                sampling_rate=16000,
                feature_dim=80,
            )
            
            # SenseVoice uses a specific encoder-decoder architecture
            # but sherpa-onnx has a specialized SenseVoice config
            # (Note: Exact config names depend on sherpa-onnx version)
            
            recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
                feat_config=feat_config,
                model_config=sherpa_onnx.OfflineModelConfig(
                    sense_voice=sherpa_onnx.OfflineSenseVoiceModelConfig(
                        model=str(model_path),
                        language="",
                        use_itn=True,
                    ),
                    tokens=str(tokens_path),
                    num_threads=4,
                    debug=False,
                    device="cpu",
                )
            )
            
            self.recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
            logger.info("✅ SenseVoice perception engine (CPU/INT8) initialized.")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load SenseVoice: {e}")
            return False

    def process_audio(self, audio_np: np.ndarray) -> Optional[dict]:
        """
        Transcribe audio and extract sensory metadata.
        Expected input: 16kHz Float32 mono.
        """
        if not self.recognizer:
            return None

        try:
            stream = self.recognizer.create_stream()
            stream.accept_waveform(16000, audio_np)
            
            self.recognizer.decode_stream(stream)
            result = stream.result.text.strip()
            
            if not result:
                return None
            
            # Extract Sensory Metadata
            emotions = self.emotion_pattern.findall(result)
            events = self.event_pattern.findall(result)
            
            # Clean text (remove tags)
            clean_text = self.emotion_pattern.sub("", result)
            clean_text = self.event_pattern.sub("", clean_text).strip()
            
            # Calibration: Extract strongest primary emotion
            primary_emotion = emotions[0] if emotions else "NEUTRAL"
            emotion_bias = self.emotion_map.get(primary_emotion, 0.0)
            
            perception_data = {
                "text": clean_text,
                "emotion": primary_emotion,
                "emotional_bias": emotion_bias,
                "events": events,
                "latency_tier": "fast"
            }
            
            logger.debug(f"Perception: {primary_emotion} | Text: {clean_text}")
            return perception_data

        except Exception as e:
            logger.error(f"SenseVoice inference error: {e}")
            return None
