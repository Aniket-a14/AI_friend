---
name: streaming-tts-pipeline
description: Patterns for a streamed LLM-to-speech pipeline -- clause-boundary chunking (not fixed word counts or timers), degenerate-fragment filtering before synthesis, sub-word stream reconstruction, control-token parsing (pauses/hesitations), audio queue backpressure, and OLA/reverb DSP correctness. Use when touching text-to-speech chunking, a TTS HTTP client, PCM audio queueing/playback, or a streaming LLM-output-to-audio pipeline (this repo: brain_agent's chunker, voice-agent's synthesis and DSP).
---

# Streaming TTS pipeline patterns

Grounded in five real defects found and fixed in this repo's voice pipeline (2026-09-01): every
pattern below traces back to a specific bug, not a hypothetical.

## Chunk boundaries: clause-driven, not timer-driven

A streamed LLM response has to be sliced into chunks for incremental synthesis, but the
slicing rule is what determines whether speech sounds natural or choppy. Two failure shapes to
watch for:

- **A latency-safety-net timer racing ahead of the semantic segmenter.** A "flush if this chunk
  has sat unflushed for N ms" fallback is legitimate (it bounds worst-case latency when the
  model stalls), but if N is set too low relative to real token inter-arrival time, it *always*
  wins the race and the semantic rule (comma/sentence-boundary scoring) never gets a chance to
  fire. Symptom: every chunk is suspiciously close to the same small word count, regardless of
  sentence structure. Fix by raising N to comfortably exceed normal per-token latency, verified
  against a *measured* real latency, not a guess -- and keep a test that the timer still fires
  as a genuine fallback when generation actually stalls, so raising it doesn't quietly disable
  it.
- **Off-by-epsilon in a summed threshold.** If a boundary score is built by summing weighted
  signals (e.g. `comma: 0.4`, `at-target-length: 0.3`) and compared with a strict `>` against a
  value those signals can sum to *exactly* (`0.7`), the single most common real trigger (a
  comma landing right at the target length) can never fire. Check whether your threshold
  comparison should be `>=`, and write a test that pins the exact boundary value your production
  config actually produces -- a test built with a different config value than production uses
  will not catch this.

Once both are fixed, "aggregate to clause boundaries" is often not a separate mechanism to
build -- verify what the two fixes *already* produce before adding more machinery. Reaching a
target word count alone, with no punctuation, should score below the flush threshold; only real
sentence-ending or comma punctuation (or a hard safety-valve word cap, for pathologically long
unpunctuated runs) should flush.

## Degenerate fragments: filter before synthesis, merge don't drop

A TTS engine will reject a punctuation-only fragment (`"..."`, `"-"`) outright. Sending it
anyway wastes a round-trip (and, worse, can get misclassified as an engine outage rather than a
bad-input rejection -- see the circuit-breaker note in rust-async-mesh-patterns). Filter such
fragments *before* the network call, and merge their characters into the nearest real clause's
text rather than dropping them outright -- most TTS engines render a trailing `"..."` as a
legitimate prosodic cue (trailing off), so gluing it onto real text is strictly better than
silence. When merging across a token boundary (a pause, a hesitation marker), move only the
*text content*, never the boundary token itself -- the pause's position and duration should be
unaffected by what punctuation got attached to which side of it. A fragment with no real text
anywhere nearby to merge into should be dropped, loudly logged (with the actual fragment
content), not silently discarded -- silent word loss is the least debuggable failure mode
available; it looks identical to a model that simply mumbles.

## Reconstructing words from a sub-word LLM token stream

An LLM's raw streaming output does not guarantee one token per whole word -- a continuation
sub-word token can arrive with no leading space of its own (`"An"` + `"ik"` + `"et"` for
"Aniket"). Naively `.split()`-ing each arriving chunk independently and treating every piece as
a complete word will insert spaces that were never in the source text. The fix is a boundary
check, not a length heuristic: before treating an incoming fragment's first token as a new word,
check **both** sides of the boundary -- does the fragment start with whitespace, or did the
text-so-far end with it? Either side carrying the separator means it's a real new word; neither
side having it means glue the fragment onto the word already in progress. Checking only one side
is a common near-miss: many legitimate word boundaries rely on the *previous* chunk's trailing
space, not the new chunk's leading one, so a one-sided check both under- and over-glues
depending on which side you picked.

If the merge can introduce punctuation the boundary-scoring logic cares about (a comma arriving
as its own continuation fragment), rescore the merged word for a possible flush -- a merge
produced outside the normal per-word loop is easy to forget to run through the same scoring
path.

**Known, accepted limit of this approach:** if a chunk gets flushed (published) in between two
fragments of the same word, the second fragment has nothing left to glue onto -- an
already-published chunk cannot be edited retroactively. This shows up as an occasional stray
leading punctuation mark on the next chunk, materially rarer and milder than the original
word-splitting bug. A full fix would mean holding back every chunk's last word pending
confirmation the next fragment doesn't continue it, trading real latency for a cosmetic edge
case -- usually not worth it.

## Control-token parsing needs a real incremental parser

Inline control markup (`<pause=200ms>`, `<hesitate>`, emotion/breath tags) mixed into the text
stream cannot be parsed with a naive substring search across streamed chunks -- if the LLM emits
`<`, `pause`, `=`, `200ms>` as separate tokens (the common case, not an edge case for many
tokenizers), a parser that only looks at one chunk at a time will miss the split tag or, worse,
leak partial tag text into the spoken output. Parse against the *accumulated* buffer with
partial-token hold-back: don't finalize a plain-text span until you've confirmed it isn't the
prefix of a recognized tag, and clamp any duration parsed from user/model-controllable markup
(a `<pause=99999ms>` from a hallucinating model should not actually pause for 100 seconds).

## Audio output queue backpressure: drop newest, never splice

When an outbound PCM queue overflows, the correct policy depends on what's being streamed. For
a *live* signal (video, a live mic feed), dropping the oldest frame to keep pace is standard.
For **synthesized speech**, the entire buffered utterance is a fixed, already-decided artifact
that must arrive intact and in order -- dropping the *oldest* frame here splices two
non-adjacent chunks of PCM together, producing an audible waveform discontinuity plus a
missing-word hole in the middle of a sentence. Prefer backpressure (block until space, if the
producer can tolerate it) or, if a bound is required, drop the *newest* incoming frame instead --
never silently reorder or splice.

## OLA crossfade and reverb: two DSP correctness traps

- **Pseudo-overlap-add that replays already-emitted audio.** Blending the tail of the
  *already-published* previous chunk into the head of the next chunk means the listener hears
  those samples twice, with a phase discontinuity at the seam. Real OLA uses complementary
  windows that sum to unity across the overlap region and consumes samples that were *held
  back*, not already sent. If true OLA is too much machinery for the win, a clean butt-join
  (no crossfade at all) is strictly better audio than replaying emitted samples.
- **A feedback delay line fed from the wrong signal.** `y[n] = x[n] + gain * y[n - D]` fed by
  writing `y` (the output) back into the delay buffer, instead of `x` (the input), turns a
  gentle echo into a runaway feedback loop -- steady-state gain approaches `1 / (1 - gain)`, and
  a `clamp()` downstream becomes a hard clipper on normal speech rather than the reverb tail it
  was meant to shape. Always feed the delay line from the *input* signal. Separately, reset the
  delay line's state per-utterance (on a `done`/end-of-turn signal), not per-chunk -- resetting
  every chunk boundary cuts off the natural echo tail exactly where it should still be ringing.
