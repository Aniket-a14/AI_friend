import hashlib
import logging
import shutil
import tarfile
from pathlib import Path

import requests

# SenseVoiceSmall (sherpa-onnx build): the acoustic emotion/event model serving the
# stt-agent's fast path. The Rust agent loads it from models/sensevoice and falls
# back to a plain Whisper fast path (words, no tone) when it is absent.
MODEL_CONFIG = {
    "name": "sense-voice-small",
    "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2",
    "expected_sha256": "C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51",
    # tokens.txt is the id->token map SenseVoice needs at load time; a stale or
    # truncated copy from a half-finished extraction would pass an existence check
    # yet break decoding, so it is pinned and verified alongside the weights.
    "expected_tokens_sha256": "F449EB28DC567533D7FA59BE34E2ABCA8784F771850C78A47FB731A31429A1DC",
    "target_dir": "models/sensevoice",
    "archive_dir_name": "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
}

logger = logging.getLogger("provision_models")

# backend/ — NOT Path(__file__).parent.parent, which is backend/scripts/. The old
# code provisioned into backend/scripts/models/sensevoice, a path nothing ever
# read, then logged success. The consumer reads backend/models/sensevoice.
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def get_file_sha256(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(1 << 16), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _verify_artifacts(model_path, tokens_path, config):
    """Both the weights and the token map must hash to their pinned checksums.

    Returns (ok, detail). Hashing tokens.txt as well as the model closes the gap
    where a corrupt token map — accepted by existence alone — would report the
    model as provisioned and then fail SenseVoice at load time.
    """
    for path, key in (
        (model_path, "expected_sha256"),
        (tokens_path, "expected_tokens_sha256"),
    ):
        sha = get_file_sha256(path)
        if sha.upper() != config[key].upper():
            return False, f"{path.name} hashed {sha}, expected {config[key]}"
    return True, None


def ensure_models_provisioned():
    """Provision SenseVoice if missing or corrupt. Raises on failure."""
    config = MODEL_CONFIG
    target_dir = BACKEND_DIR / config["target_dir"]
    model_path = target_dir / "model.int8.onnx"
    tokens_path = target_dir / "tokens.txt"

    # A directory that exists but lacks the model is half-provisioned, not
    # provisioned: the old check skipped it silently and the agent then failed at
    # load time with no hint that provisioning was the culprit.
    if model_path.exists() and tokens_path.exists():
        ok, detail = _verify_artifacts(model_path, tokens_path, config)
        if ok:
            logger.info("✅ SenseVoice model + tokens verified (SHA256 match).")
            return
        logger.warning("🚨 SenseVoice artifacts failed verification (%s); re-provisioning.", detail)
    else:
        logger.info("SenseVoice model not provisioned; downloading %s...", config["name"])

    _provision_model(config, target_dir)

    # Trust nothing until both artifacts on disk hash correctly. The old flow
    # logged success straight after extraction, so a truncated or tampered
    # download became "provisioned" until some later run happened to re-hash it.
    ok, detail = _verify_artifacts(model_path, tokens_path, config)
    if not ok:
        raise RuntimeError(
            f"SenseVoice provisioning verification failed: {detail}. "
            "Refusing to report success."
        )
    logger.info("✨ SenseVoice provisioned and verified in %s", target_dir)


def _provision_model(config, target_path: Path):
    """Download and extract the model archive, replacing whatever is present.

    The old version early-returned "already provisioned" whenever the target
    directory existed — including when it was called *because* the checksum
    failed. The re-provisioning path was a no-op that logged success.
    """
    models_dir = target_path.parent
    temp_download = models_dir / "temp_model.tar.bz2"
    extracted_dir = models_dir / config["archive_dir_name"]

    models_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Clear leftovers from a previous failed run so stale files cannot
        # satisfy later existence checks with a mismatched set.
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir)

        logger.info(
            "📥 Downloading %s (expected SHA256 %s…)",
            config["name"],
            config["expected_sha256"][:8],
        )
        response = requests.get(config["url"], stream=True, timeout=300)
        response.raise_for_status()
        with open(temp_download, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 16):
                f.write(chunk)

        logger.info("📦 Extracting model weights...")
        with tarfile.open(temp_download, "r:bz2") as tar:
            # filter="data" refuses absolute paths, ".." traversal and special
            # file types (CVE-2007-4559).
            tar.extractall(path=models_dir, filter="data")

        if not extracted_dir.is_dir():
            raise RuntimeError(
                f"archive did not contain expected directory {extracted_dir.name}; "
                "the upstream release layout may have changed"
            )

        # Replace, never merge: merging an old target with a new extraction can
        # pair a model with tokens from a different release.
        if target_path.exists():
            shutil.rmtree(target_path)
        extracted_dir.rename(target_path)
    finally:
        if temp_download.exists():
            temp_download.unlink()
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure_models_provisioned()
