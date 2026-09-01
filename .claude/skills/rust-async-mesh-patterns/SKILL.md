---
name: rust-async-mesh-patterns
description: Async Rust patterns for a NATS/JetStream-coordinated mesh of independent service processes -- ack timing, JetStream vs core NATS publish, circuit breakers around a flaky downstream HTTP dependency, retry-with-backoff that knows when NOT to retry, background readiness probes, and shared-mutable-state across tokio tasks. Use when touching a Rust crate that talks to NATS or a downstream HTTP service in a retry/circuit-breaker loop (this repo: voice-agent, stt-agent).
---

# Rust async mesh patterns (tokio + async-nats)

Grounded in this repo's `voice-agent`/`stt-agent` crates -- a mesh of independent Rust/Python
processes coordinated over NATS JetStream, not function calls. The patterns below are the ones
that recur across that boundary.

## JetStream vs. core NATS publish

`js.publish(...)` (JetStream) gives you a durable, at-least-once stream with replay and
consumer-group semantics. `nc.publish(...)` (core NATS, no `js.` prefix) is fire-and-forget --
but if a JetStream-backed stream's subject wildcard already covers the subject (e.g. an
`"audio.>"` stream catching a `nc.publish("audio.inbound", ...)`), the JetStream consumer still
receives it. This matters for debugging/scripting: you do not need `js.publish` to exercise a
JetStream consumer end-to-end, a raw core publish to a subject the stream already covers is
enough, and is the simpler tool for a one-off synthetic test message.

## Ack timing is a real correctness axis, not a formality

A subscription framework that acks *after* the callback returns (common, and correct for most
consumers) has one sharp edge: if a single callback invocation can legitimately run long (a
multi-second LLM generation, a multi-minute batch job), it can outlive the broker's default
AckWait, causing a spurious redelivery of a message that is still being processed. Two real
fixes, not band-aids:
- Raise `AckWait` on that specific consumer to comfortably exceed the callback's worst-case
  runtime (a config value, set once at stream/consumer setup, not scattered per-call).
- Or ack early/manually inside the callback once the work is durably queued elsewhere, rather
  than at the very end of a long-running handler.
Do not "fix" this by shortening the handler's actual work; that just moves the deadline problem
elsewhere. Identify long-running consumers explicitly and give them their own AckWait.

## Circuit breaker around a flaky downstream (e.g. a local inference server)

Structure, not just intent:
```rust
struct CircuitBreaker { /* failure count, opened_at, cooldown */ }
impl CircuitBreaker {
    fn is_open(&self, now_ms: u64) -> bool { /* true once threshold crossed, until cooldown elapses */ }
    fn record_success(&self) { /* resets failure count; a half-open trial success closes it */ }
    fn record_failure(&self, now_ms: u64) { /* increments; opens at threshold */ }
}
```
Call site pattern: check `is_open()` *before* attempting the call (skip the round-trip and its
timeout entirely once already known-down -- don't rediscover the same outage every request), and
route `Ok`/`Err` of the actual attempt into `record_success`/`record_failure`. Half-open trial:
after cooldown, allow exactly one attempt through; a failure re-arms the full cooldown rather
than letting a flapping dependency's near-misses reset the clock repeatedly.

**Correctness trap:** not every `Err` from the downstream means "the service is down." A
downstream that returns a deterministic validation rejection (bad input, not a broken server)
should **not** open the circuit breaker and should **not** be retried -- see the retry section
below. Conflating "your request was malformed" with "the server is unhealthy" makes the breaker
trip on garbage input instead of real outages, and wastes the retry budget on something that
will fail identically every time.

## Retry-with-backoff that knows when not to retry

```rust
const MAX_ATTEMPTS: u32 = 3;
const BACKOFF_MS: [u64; 2] = [150, 400];

for attempt in 0..MAX_ATTEMPTS {
    match try_once().await {
        Ok(v) => return Ok(v),
        Err(e) if is_non_retryable(&e) => return Err(e),   // deterministic rejection: stop now
        Err(e) => {
            warn!(attempt, error = %e, "attempt failed");
            if let Some(&delay) = BACKOFF_MS.get(attempt as usize) {
                tokio::time::sleep(Duration::from_millis(delay)).await;
            }
        }
    }
}
```
Distinguish the two error classes with a real type (a small `#[derive(Debug)] struct
SomethingRejected` implementing `std::error::Error`, checked via `err.downcast_ref::<...>()`),
not a string match on the error message -- string matching breaks the moment the downstream's
wording changes, a typed marker does not. Log the non-retryable case loudly and include what was
actually rejected; that is usually the one piece of context a generic retry-exhausted log line
omits.

## Background readiness probes that catch "up but broken," not just "unreachable"

A plain connectivity/status-code health check misses a server that accepts a request, returns
`200`, and then produces an empty or garbage body (a known failure mode for some streaming
inference servers under load). Probe with a real, cheap request and check the *payload*, not
just the status:
```rust
async fn probe(...) -> Result<()> {
    let mut resp = real_request(PROBE_PHRASE).await?;
    match resp.chunk().await? {
        Some(bytes) if !bytes.is_empty() => Ok(()),
        _ => bail!("readiness probe got an empty response body"),
    }
}
```
Run it on an interval via `tokio::spawn`, independent of live traffic, so an outage is caught
(and recovery detected) even during silence -- a live user-facing request should never be the
first thing to discover the dependency is down. Make the interval configurable and support `0`
to disable it cleanly for local dev against a mock/absent backend, rather than spamming warnings
every tick for no operational benefit.

## Shared mutable state across mesh tasks

Values read by one task and written by another (an attenuation factor set by a barge-in
handler, a noise-scale factor set by a config-feedback subscriber) belong behind
`Arc<Mutex<T>>` (or `std::sync::Mutex` for a `f64`/small-copy type accessed briefly, non-async
lock) -- read it once into a local at the top of the hot path (`if let Ok(guard) = x.lock() {
*guard } else { fallback }`), never hold the lock across an `.await`. A poisoned lock (a panic
while held) should fall back to a safe default, not propagate the panic into an unrelated audio
frame or request.

## Testing HTTP-facing async Rust without touching the real network

Use `wiremock` (`MockServer::start().await`, `Mock::given(...).respond_with(...).mount(&server)`)
and point the code under test at `server.uri()`. `.expect(N)` on a mock is itself an assertion:
it fails the test if the code makes a different number of calls than expected -- this is the
right tool for proving a retry *did not* fire (`.expect(1)`) as much as proving it did
(`.expect(MAX_ATTEMPTS)`).
