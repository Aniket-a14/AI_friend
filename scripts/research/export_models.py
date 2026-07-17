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
            # filter="data" refuses members with absolute paths, ".." traversal,
            # or special file types. Without it a malicious archive can write
            # anywhere on disk (CVE-2007-4559); it also becomes the interpreter
            # default in a future Python, so setting it explicitly keeps
            # behaviour stable across versions.
            tar.extractall(path=MODELS_DIR, filter="data")

        extracted_dir = MODELS_DIR / "vits-piper-en_US-amy-low"
        if not extracted_dir.exists():
            raise RuntimeError(
                f"expected {extracted_dir} in the archive but it was not extracted; "
                "the upstream release layout may have changed"
            )

        # Move key assets to base model directory
        shutil.move(str(extracted_dir / "en_US-amy-low.onnx"), str(model_file))
        shutil.move(str(extracted_dir / "lexicon.txt"), str(lexicon_file))
        shutil.move(str(extracted_dir / "tokens.txt"), str(tokens_file))

        shutil.rmtree(extracted_dir)

        logger.info(
            "✨ Base ONNX fallback model provisioned successfully in models/base/"
        )
    except Exception:
        # Do not report success for a voice that was not provisioned: this is now
        # the only real local voice, since custom export is unimplemented.
        logger.exception("❌ Failed to provision base models")
        raise
    finally:
        if TEMP_FILE.exists():
            os.remove(TEMP_FILE)


PLACEHOLDER_MARKER = b"MOCK_"
CUSTOM_ARTIFACTS = ("custom_gpt.onnx", "custom_vits.onnx")


def purge_placeholder_artifacts():
    """Delete fake ``*.onnx`` files left by the old placeholder export.

    An earlier version of this script wrote text files containing
    ``MOCK_CUSTOM_*_ONNX_CONTENT`` under those names and logged success. They are
    not models: ONNX Runtime cannot parse them, and because the voice agent tries
    ``models/custom/`` first, their mere presence used to disable local synthesis
    entirely. Anyone who ran the old script still has them on disk, so clean them
    up here.

    Only files whose contents carry the placeholder marker are removed — a real
    exported model is never touched.
    """
    removed = 0
    for name in CUSTOM_ARTIFACTS:
        path = CUSTOM_DIR / name
        if not path.exists():
            continue
        try:
            head = path.read_bytes()[: len(PLACEHOLDER_MARKER)]
        except OSError as e:
            logger.warning("Could not inspect %s: %s", path, e)
            continue
        if head == PLACEHOLDER_MARKER:
            path.unlink()
            removed += 1
            logger.warning(
                "Removed placeholder %s — it was a text file, not an ONNX model.",
                path,
            )
    return removed


def export_custom_models():
    """Export custom GPT-SoVITS checkpoints to ONNX.

    NOT IMPLEMENTED. This previously *simulated* the export by writing text files
    named ``custom_gpt.onnx`` / ``custom_vits.onnx`` and logging
    "✅ Custom ONNX models exported successfully" — a success message for work that
    never happened, producing artifacts that actively broke local synthesis.

    Returning False (rather than faking output) means the voice agent falls back to
    the real base model in ``models/base/``.

    To implement: install GPT-SoVITS and call its exporter, roughly::

        from GPT_SoVITS.export_onnx import export_gpt, export_sovits

    writing real ``custom_gpt.onnx`` / ``custom_vits.onnx`` plus the matching
    ``lexicon.txt`` and ``tokens.txt`` into ``models/custom/``.
    """
    purge_placeholder_artifacts()

    gpt_weights_dir = MODELS_DIR / "GPT_weights"
    sovits_weights_dir = MODELS_DIR / "SoVITS_weights"

    custom_gpt_ckpt = gpt_weights_dir / "ai_friend_voice.ckpt"
    custom_sovits_pth = sovits_weights_dir / "ai_friend_voice.pth"

    if not (custom_gpt_ckpt.exists() and custom_sovits_pth.exists()):
        logger.info("Custom GPT-SoVITS checkpoints not found. Using base voice.")
        return False

    logger.error(
        "Custom GPT-SoVITS checkpoints were found at:\n"
        "    %s\n"
        "    %s\n"
        "but ONNX export for them is NOT IMPLEMENTED, so they cannot be used. "
        "The base voice in models/base/ will be used instead. Implement the "
        "GPT-SoVITS exporter in export_custom_models() to enable the custom voice.",
        custom_gpt_ckpt,
        custom_sovits_pth,
    )
    return False


def main():
    # Base first: it is the only voice that actually works today, so provision it
    # before anything that might fail.
    ensure_base_models()

    # Purges stale placeholder artifacts and reports honestly that custom export
    # is unimplemented. Never fabricates output.
    export_custom_models()


if __name__ == "__main__":
    main()
