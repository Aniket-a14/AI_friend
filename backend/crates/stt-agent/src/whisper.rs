//! Real speech recognition backed by whisper.cpp (via `whisper-rs`).
//!
//! Dual-path design: a small `fast` model produces low-latency speculative
//! hypotheses for barge-in arbitration, while a larger `accurate` model produces
//! the final transcript that drives cognition. Both are Whisper — the historical
//! docs described the fast path as SenseVoice, but that is a sherpa-onnx model and
//! is not available through whisper.cpp. Emotion / paralinguistic events are
//! therefore NOT inferred here; those fields are left empty rather than fabricated.

use anyhow::{Context, Result};
use std::path::{Path, PathBuf};
use tokio::io::AsyncWriteExt;
use tracing::{info, warn};
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

/// Upstream ggml weights published alongside whisper.cpp.
const MODEL_BASE_URL: &str = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main";

pub struct WhisperModel {
    ctx: WhisperContext,
    label: &'static str,
    language: String,
}

impl WhisperModel {
    pub fn load(path: &Path, label: &'static str, language: &str) -> Result<Self> {
        // `new_with_params` is generic over `AsRef<Path>`, so the path goes in directly.
        let ctx = WhisperContext::new_with_params(path, WhisperContextParameters::default())
            .with_context(|| format!("load whisper model '{label}' from {}", path.display()))?;

        info!(model = label, path = %path.display(), "loaded whisper model");
        Ok(Self {
            ctx,
            label,
            language: language.to_string(),
        })
    }

    /// Transcribe mono 16 kHz f32 PCM. Returns the concatenated segment text.
    ///
    /// This is synchronous, CPU-bound work — callers must run it off the async
    /// runtime (e.g. `tokio::task::spawn_blocking`).
    pub fn transcribe(&self, pcm_16k: &[f32]) -> Result<String> {
        // whisper.cpp needs at least ~1 second of audio to produce a usable mel
        // window; shorter buffers yield garbage or an internal error.
        if pcm_16k.len() < 16_000 / 2 {
            return Ok(String::new());
        }

        let mut state = self
            .ctx
            .create_state()
            .with_context(|| format!("create whisper state for '{}'", self.label))?;

        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        params.set_language(Some(self.language.as_str()));
        params.set_translate(false);
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(false);
        params.set_suppress_blank(true);
        // Single-segment decoding keeps latency predictable for short utterances.
        params.set_n_threads(recommended_threads());

        state
            .full(params, pcm_16k)
            .with_context(|| format!("whisper inference failed for '{}'", self.label))?;

        // whisper-rs 0.16 exposes segments through an iterator; `to_str_lossy`
        // replaces invalid UTF-8 rather than failing the whole utterance, which
        // matters because whisper can emit partial multi-byte tokens.
        let mut text = String::new();
        for segment in state.as_iter() {
            match segment.to_str_lossy() {
                Ok(s) => text.push_str(&s),
                Err(err) => warn!(
                    model = self.label,
                    "skipping undecodable whisper segment: {err}"
                ),
            }
        }

        Ok(clean_transcript(&text))
    }
}

fn recommended_threads() -> std::os::raw::c_int {
    let cores = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4);
    // Cap so a transcription cannot starve the rest of the mesh on small hosts.
    cores.clamp(1, 8) as std::os::raw::c_int
}

/// Strip whisper.cpp's non-speech annotations and normalise whitespace.
///
/// whisper emits bracketed markers such as `[BLANK_AUDIO]`, `(wind blowing)` and
/// `[Music]` for non-speech. Publishing those onto `chat.input` would make the
/// agent "hear" sound effects as user utterances.
pub fn clean_transcript(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut depth_square = 0usize;
    let mut depth_round = 0usize;

    for ch in raw.chars() {
        match ch {
            '[' => depth_square += 1,
            ']' => depth_square = depth_square.saturating_sub(1),
            '(' => depth_round += 1,
            ')' => depth_round = depth_round.saturating_sub(1),
            _ if depth_square == 0 && depth_round == 0 => out.push(ch),
            _ => {}
        }
    }

    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Resolve a model file, downloading it into the cache directory on first use.
pub async fn ensure_model(cache_dir: &Path, model_name: &str) -> Result<PathBuf> {
    tokio::fs::create_dir_all(cache_dir)
        .await
        .with_context(|| format!("create model cache dir {}", cache_dir.display()))?;

    let file_name = format!("ggml-{model_name}.bin");
    let target = cache_dir.join(&file_name);

    if tokio::fs::try_exists(&target).await.unwrap_or(false) {
        let size = tokio::fs::metadata(&target).await.map(|m| m.len()).unwrap_or(0);
        if size > 1_000_000 {
            info!(model = model_name, path = %target.display(), size, "using cached whisper model");
            return Ok(target);
        }
        warn!(
            path = %target.display(),
            size,
            "cached whisper model looks truncated; re-downloading"
        );
        let _ = tokio::fs::remove_file(&target).await;
    }

    let url = format!("{MODEL_BASE_URL}/{file_name}");
    info!(model = model_name, %url, "downloading whisper model (first run only)");

    let mut response = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(1800))
        .build()?
        .get(&url)
        .send()
        .await
        .with_context(|| format!("download {url}"))?
        .error_for_status()
        .with_context(|| format!("download {url}"))?;

    // Write to a temp path then rename, so a crash mid-download cannot leave a
    // corrupt file that later looks like a valid cache hit.
    //
    // Streamed chunk-by-chunk rather than via `response.bytes()`, which would hold
    // the entire model in memory before the first byte reaches disk — a spike as
    // large as the model itself (hundreds of MB for the larger ggml weights) at
    // startup, inside a memory-capped container, purely to write a file.
    let tmp = target.with_extension("part");
    let mut file = tokio::fs::File::create(&tmp)
        .await
        .with_context(|| format!("create {}", tmp.display()))?;

    let mut written: u64 = 0;
    while let Some(chunk) = response.chunk().await.context("read model body")? {
        file.write_all(&chunk)
            .await
            .with_context(|| format!("write {}", tmp.display()))?;
        written += chunk.len() as u64;
    }
    file.flush()
        .await
        .with_context(|| format!("flush {}", tmp.display()))?;
    drop(file);

    tokio::fs::rename(&tmp, &target)
        .await
        .with_context(|| format!("finalise {}", target.display()))?;

    info!(model = model_name, bytes = written, "whisper model ready");
    Ok(target)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_strips_bracketed_non_speech() {
        assert_eq!(clean_transcript(" [BLANK_AUDIO] "), "");
        assert_eq!(clean_transcript("[Music] hello there"), "hello there");
        assert_eq!(clean_transcript("hello (wind blowing) world"), "hello world");
    }

    #[test]
    fn clean_normalises_whitespace() {
        assert_eq!(clean_transcript("  hello   there \n world "), "hello there world");
    }

    #[test]
    fn clean_keeps_plain_speech_intact() {
        assert_eq!(clean_transcript("Turn the lights off."), "Turn the lights off.");
    }
}
