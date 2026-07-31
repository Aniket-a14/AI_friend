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
# Uses `sample_en_gold.wav`, the same stock reference clip
# sovits_bootstrap.sh's own warmup step already trusts to be present under
# ./backend/voice_samples -- not the deployment's possibly-customized
# REF_AUDIO_PATH, since this only needs to prove the engine itself works, not
# exercise any particular cloned voice.
set -euo pipefail

OUT="/tmp/sovits_healthcheck_response.raw"

curl -fsS -m 8 -X POST "http://127.0.0.1:9871/tts" \
     -H "Content-Type: application/json" \
     -d '{
            "text": "Status check.",
            "text_lang": "en",
            "ref_audio_path": "output/sample_en_gold.wav",
            "prompt_text": "At the end of the exam, the program shows the performance summary.",
            "prompt_lang": "en",
            "text_split_method": "cut5",
            "batch_size": 1,
            "media_type": "raw",
            "streaming_mode": 0
          }' \
     -o "$OUT"

# A 200 with an empty body is still curl-successful -- GPT-SoVITS has open
# reports of returning blank audio under load, which this exists to catch.
[ -s "$OUT" ]
