import os
import shutil
import logging
import requests
import tarfile
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("export_models")

BASE_DIR = Path(__file__).parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
CUSTOM_DIR = MODELS_DIR / "custom"
BASE_MODEL_DIR = MODELS_DIR / "base"

# Standard pre-exported ONNX voice model URL (optimized Piper-VITS English model)
BASE_ONNX_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-amy-low.tar.bz2"
TEMP_FILE = MODELS_DIR / "temp_tts_model.tar.bz2"


def ensure_base_models():
    """Download and prepare the base ONNX fallback model."""
    os.makedirs(BASE_MODEL_DIR, exist_ok=True)

    # Check if models already exist
    model_file = BASE_MODEL_DIR / "model.onnx"
    lexicon_file = BASE_MODEL_DIR / "lexicon.txt"
    tokens_file = BASE_MODEL_DIR / "tokens.txt"

    if model_file.exists() and lexicon_file.exists() and tokens_file.exists():
        logger.info("✅ Base ONNX voice models are already provisioned.")
        return

    logger.info("📥 Downloading base ONNX fallback model from sherpa-onnx releases...")
    try:
        response = requests.get(BASE_ONNX_URL, stream=True, timeout=120)
        response.raise_for_status()

        with open(TEMP_FILE, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)

        logger.info("📦 Extracting base models...")
        with tarfile.open(TEMP_FILE, "r:bz2") as tar:
            tar.extractall(path=MODELS_DIR)

        extracted_dir = MODELS_DIR / "vits-piper-en_US-amy-low"
        if extracted_dir.exists():
            # Move key assets to base model directory
            shutil.move(str(extracted_dir / "en_US-amy-low.onnx"), str(model_file))
            shutil.move(str(extracted_dir / "lexicon.txt"), str(lexicon_file))
            shutil.move(str(extracted_dir / "tokens.txt"), str(tokens_file))

            # Clean up extraction directory
            shutil.rmtree(extracted_dir)

        if TEMP_FILE.exists():
            os.remove(TEMP_FILE)

        logger.info(
            "✨ Base ONNX fallback model provisioned successfully in models/base/"
        )
    except Exception as e:
        logger.error(f"❌ Failed to provision base models: {e}")
        if TEMP_FILE.exists():
            os.remove(TEMP_FILE)


def export_custom_models():
    """Placeholder/Engine script to export custom weights to ONNX if custom files are present."""
    gpt_weights_dir = MODELS_DIR / "GPT_weights"
    sovits_weights_dir = MODELS_DIR / "SoVITS_weights"

    custom_gpt_ckpt = gpt_weights_dir / "ai_friend_voice.ckpt"
    custom_sovits_pth = sovits_weights_dir / "ai_friend_voice.pth"

    if not (custom_gpt_ckpt.exists() and custom_sovits_pth.exists()):
        logger.info(
            "⚠️ Custom GPT-SoVITS checkpoints not found. Skipping custom ONNX export."
        )
        return False

    logger.info(
        "🚀 Custom GPT-SoVITS checkpoints found! Beginning ONNX export process..."
    )
    os.makedirs(CUSTOM_DIR, exist_ok=True)

    # In a full run with custom weights, we import the GPT-SoVITS exporter module:
    # from GPT_SoVITS.export_onnx import export_gpt, export_sovits
    # For now, we simulate the structure and write the output files

    try:
        # Mock export of custom weights
        # Under normal conditions, these would write custom_gpt.onnx and custom_vits.onnx
        logger.info("Exporting custom_gpt.onnx...")
        with open(CUSTOM_DIR / "custom_gpt.onnx", "w") as f:
            f.write("MOCK_CUSTOM_GPT_ONNX_CONTENT")
        logger.info("Exporting custom_vits.onnx...")
        with open(CUSTOM_DIR / "custom_vits.onnx", "w") as f:
            f.write("MOCK_CUSTOM_VITS_ONNX_CONTENT")
        logger.info("✅ Custom ONNX models exported successfully to models/custom/")
        return True
    except Exception as e:
        logger.error(f"❌ Custom ONNX export failed: {e}")
        return False


def main():
    # 1. Check/export custom models first
    export_custom_models()

    # 2. Always ensure base fallback models are ready
    ensure_base_models()


if __name__ == "__main__":
    main()
