#!/bin/bash
# 🚀 GPT-SoVITS Sovereignty Bootstrap Script
# Targets: Persistent Identity + Zero-Latency Warmup

set -Eeuo pipefail

# 1. Hardware Autodetect (Laptop vs. 2060 Super)
echo "🧬 Detecting Hardware Profile..."
if command -v nvidia-smi &> /dev/null && nvidia-smi -L &> /dev/null; then
    echo "🚀 NVIDIA GPU Detected. Enabling Production Mode (FP16/CUDA)."
    export is_half=${is_half:-true}
    export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
    DEVICE_FLAG="cuda"
else
    echo "💻 No NVIDIA GPU found (Laptop/CPU Mode). Falling back to FP32/CPU."
    export is_half=false
    export CUDA_VISIBLE_DEVICES=-1
    DEVICE_FLAG="cpu"
fi

# 2. Start core API server in background
echo "🎙️ Starting GPT-SoVITS API Server ($DEVICE_FLAG)..."
python api_v2.py -a 0.0.0.0 -p 9871 &
SERVER_PID=$!
API_READY_TIMEOUT_SECONDS=${API_READY_TIMEOUT_SECONDS:-300}

cleanup() {
    kill "$SERVER_PID" 2>/dev/null || true
    for _ in 1 2 3; do
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            return
        fi
        sleep 1
    done
    kill -9 "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

curl_retry() {
    curl -fS --retry 5 --retry-delay 2 "$@"
}

# 2. Wait for API to reach readiness
echo "⏳ Waiting for API readiness..."
elapsed=0
until curl_retry http://127.0.0.1:9871/docs > /dev/null; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "❌ SoVITS API process exited before becoming ready."
    exit 1
  fi
  if [ "$elapsed" -ge "$API_READY_TIMEOUT_SECONDS" ]; then
    echo "❌ SoVITS API readiness timed out after ${API_READY_TIMEOUT_SECONDS}s."
    exit 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done
echo "✅ SoVITS API is Online."

# 3. Dynamic Identity Injection (Persistent Weights)
if [ -n "${CUSTOM_GPT_PATH:-}" ] && [ -f "$CUSTOM_GPT_PATH" ]; then
    echo "⚖️ Pre-loading GPT Weights: $CUSTOM_GPT_PATH"
    curl_retry -G \
      --data-urlencode "weights_path=$CUSTOM_GPT_PATH" \
      "http://127.0.0.1:9871/set_gpt_weights" > /dev/null
else
    echo "⚠️ Custom GPT weights file not found on disk ($CUSTOM_GPT_PATH). Skipping pre-load."
fi

if [ -n "${CUSTOM_SOVITS_PATH:-}" ] && [ -f "$CUSTOM_SOVITS_PATH" ]; then
    echo "⚖️ Pre-loading SoVITS Weights: $CUSTOM_SOVITS_PATH"
    curl_retry -G \
      --data-urlencode "weights_path=$CUSTOM_SOVITS_PATH" \
      "http://127.0.0.1:9871/set_sovits_weights" > /dev/null
else
    echo "⚠️ Custom SoVITS weights file not found on disk ($CUSTOM_SOVITS_PATH). Skipping pre-load."
fi

# 4. Identity Warmup (Populate BERT/HuBERT Latent Caches)
# We perform a dummy synthesis with the neutral anchor to 'prime' the GPU.
# Reads REF_AUDIO_PATH/REF_TEXT (same vars voice_agent and the healthcheck
# read) instead of hardcoding, and skips rather than hangs if that clip is
# genuinely absent -- a warmup call against a missing reference clip cannot
# succeed, and this must not block server startup on it.
REF_AUDIO_PATH="${REF_AUDIO_PATH:-output/sample_en_gold.wav}"
REF_TEXT="${REF_TEXT:-At the end of the exam, the program shows the performance summary.}"

json_payload() {
    python3 - "$REF_AUDIO_PATH" "$REF_TEXT" <<'PY'
import json
import sys

print(json.dumps({
    "text": "Warmup segment.",
    "text_lang": "en",
    "ref_audio_path": sys.argv[1],
    "prompt_text": sys.argv[2],
    "prompt_lang": "en",
    "streaming_mode": 0,
}))
PY
}

if [ -n "${CUSTOM_GPT_PATH:-}" ] && [ -f "${CUSTOM_GPT_PATH:-}" ] && [ -n "${CUSTOM_SOVITS_PATH:-}" ] && [ -f "${CUSTOM_SOVITS_PATH:-}" ]; then
    if [ ! -f "/workspace/GPT-SoVITS/${REF_AUDIO_PATH}" ]; then
        echo "⚠️ Reference clip ${REF_AUDIO_PATH} not found. Skipping Warmup."
    else
        echo "🔥 Performing Identity Warmup (BERT/HuBERT Cache)..."
        curl_retry -X POST "http://127.0.0.1:9871/tts" \
             -H "Content-Type: application/json" \
             -d "$(json_payload)" > /dev/null

        echo "✅ Identity 'ai_friend_voice' is Warm. System is Ready."
    fi
else
    echo "⚠️ Custom weights not found on disk. Skipping Warmup."
fi

# 5. Keep process in foreground
trap - EXIT
wait $SERVER_PID
