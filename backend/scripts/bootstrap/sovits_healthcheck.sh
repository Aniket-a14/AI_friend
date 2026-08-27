#!/bin/bash
# Real-synthesis readiness probe for GPT-SoVITS, run as the container
# healthcheck. The previous check (`wget --spider /docs`) only proved the
# process was accepting connections -- it said nothing about whether the
# loaded model can actually render audio. This POSTs a short canned phrase to
# the real /tts endpoint (the same one voice-agent calls at runtime) and fails
# unless a non-empty body comes back, catching the "up but broken" case
# (blank-WAV responses under streaming load, a wedged CUDA context) that a
# status-only ping misses.
#
# Reads REF_AUDIO_PATH/REF_TEXT (same vars voice_agent reads) rather than
# hardcoding, defaulting to the bundled `sample_en_gold.wav` from Phase 1.1.
# If the resolved clip is genuinely absent -- before ensure_default_voice_
# sample.py has run, or a custom REF_AUDIO_PATH pointing nowhere -- a real
# synthesis call can never succeed, so this degrades to a liveness-only probe
# instead of failing forever and permanently blocking voice_agent's
# `service_healthy` gate on an invisible dependency deadlock.
set -euo pipefail

REF_AUDIO_PATH="${REF_AUDIO_PATH:-output/sample_en_gold.wav}"
REF_TEXT="${REF_TEXT:-At the end of the exam, the program shows the performance summary.}"
# Overridable only so tests can point this at a fake root; production always
# runs inside the container where GPT-SoVITS's own working directory is this.
SOVITS_ROOT="${SOVITS_ROOT:-/workspace/GPT-SoVITS}"

OUT="/tmp/sovits_healthcheck_response.raw"

# ref_audio_path is resolved by GPT-SoVITS relative to its own working
# directory, which is where `output/` is bind-mounted from
# backend/voice_samples/.
if [ ! -f "${SOVITS_ROOT}/${REF_AUDIO_PATH}" ]; then
    echo "sovits_healthcheck: ${REF_AUDIO_PATH} not found, degrading to liveness-only probe" >&2
    curl -fsS -m 8 "http://127.0.0.1:9871/docs" -o /dev/null
    exit 0
fi

curl -fsS -m 8 -X POST "http://127.0.0.1:9871/tts" \
     -H "Content-Type: application/json" \
     -d "{
            \"text\": \"Status check.\",
            \"text_lang\": \"en\",
            \"ref_audio_path\": \"${REF_AUDIO_PATH}\",
            \"prompt_text\": \"${REF_TEXT}\",
            \"prompt_lang\": \"en\",
            \"text_split_method\": \"cut5\",
            \"batch_size\": 1,
            \"media_type\": \"raw\",
            \"streaming_mode\": 0
          }" \
     -o "$OUT"

# A 200 with an empty body is still curl-successful -- GPT-SoVITS has open
# reports of returning blank audio under load, which this exists to catch.
[ -s "$OUT" ]
