# Bundled voice asset provenance

Both `.wav` files here are synthesized locally with macOS's built-in `say`
command (`Alex` voice, offline, no network call), not sourced from a
third-party recording. They are software-generated speech shipped so a fresh
clone produces audible, same-voice output before anyone records their own —
neither is meant to represent a specific person.

- `default_voice.wav` -- the neutral reference clip (`RefClip`, see
  `backend/crates/voice-agent/src/main.rs`) that steers GPT-SoVITS delivery
  for one utterance; it does not encode identity.
- `voice_engine_unavailable.wav` -- the same-voice fallback `load_vocalization_
  pcm` plays instead of dropping a turn silently when live synthesis fails.
  Deliberately in the same placeholder voice as `default_voice.wav`, so the
  degradation stays same-voice rather than a different or synthetic one.
  `breath_fast.wav`/`sigh_soft.wav` are non-verbal sound effects `say` cannot
  produce and are intentionally not shipped here -- see roadmap Phase 1.5 and
  2.3; `load_vocalization_pcm` already degrades to logged silence for them.

Regenerate with:

```bash
say -v Alex -r 150 -o default_voice.aiff "$(cat default_voice.txt)"
afconvert -f WAVE -d LEI16@32000 -c 1 default_voice.aiff default_voice.wav

say -v Alex -r 150 -o voice_engine_unavailable.aiff "$(cat voice_engine_unavailable.txt)"
afconvert -f WAVE -d LEI16@32000 -c 1 voice_engine_unavailable.aiff voice_engine_unavailable.wav
```

No attribution or license restrictions apply to these files beyond the
repository's own `LICENSE`.
