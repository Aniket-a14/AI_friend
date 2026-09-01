# Bundled voice asset provenance

Both `.wav` files here are outputs of a GPT-SoVITS model fine-tuned on a real
human voice contributor's recordings, conditioned on a trimmed clip of that
same recorded voice. They are **not** synthetic placeholder speech and they
**do** encode a real person's vocal identity by design — this is the
project's actual voice, used deliberately as one of its showcased
identities (site, pitch material, demos), not a stand-in awaiting
replacement.

- `default_voice.wav` -- the neutral reference clip (`RefClip`, see
  `backend/crates/voice-agent/src/main.rs`) that steers GPT-SoVITS delivery
  for one utterance. Its spoken content matches `default_voice.txt` exactly
  (required for reference-conditioned synthesis to stay aligned).
- `voice_engine_unavailable.wav` -- the same-voice fallback `load_vocalization_
  pcm` plays instead of dropping a turn silently when live synthesis fails.
  Regenerated in the cloned voice (not the old synthetic placeholder) so the
  degradation stays same-voice rather than switching identity mid-fallback.
  `breath_fast.wav`/`sigh_soft.wav` are non-verbal sound effects outside this
  pipeline's scope and are intentionally not shipped here -- see roadmap
  Phase 1.5 and 2.3; `load_vocalization_pcm` already degrades to logged
  silence for them.

**Consent.** The voice contributor has given explicit consent for this
recording and its fine-tuned derivative to be used in this repository and in
the project's public-facing and commercial representations (website,
pitch/demo material). Per this project's standing convention, the
contributor's name is deliberately not recorded in this file or elsewhere in
the repository, commit history, or issue tracker.

Regenerate `default_voice.wav` by fine-tuning GPT-SoVITS on the contributor's
source recordings (see `.agents/CONTEXT.md` for the training pipeline and
provenance of the current weights) and synthesizing `default_voice.txt`
through the resulting model, conditioned on a 3-10s trimmed clip of the same
recordings. Regenerate `voice_engine_unavailable.wav` the same way, from
`voice_engine_unavailable.txt`, through the same fine-tuned model.

No attribution or license restrictions apply to these files beyond the
repository's own `LICENSE` and the consent recorded above.
