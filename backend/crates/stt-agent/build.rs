//! Windows-only workaround for a DLL shadowing trap that crashes the test suite.
//!
//! sherpa-onnx-sys copies its runtime DLLs (sherpa-onnx-c-api.dll plus its bundled
//! onnxruntime.dll) into `target/<profile>/`, but test executables run from
//! `target/<profile>/deps/`. Windows resolves DLLs by searching the executable's
//! own directory first, then **System32 — which comes before PATH** — and Windows 11
//! ships its own `onnxruntime.dll` (Windows ML, ORT 1.17) in System32. The result:
//! sherpa's C API, built against a newer ONNX Runtime, loads the OS's 1.17 runtime,
//! prints "The requested API version [27] is not available", and dies with an
//! access violation. `cargo test -p stt-agent` then fails on any stock Windows 11
//! machine even though every crate built cleanly.
//!
//! Staging the DLLs next to the test binaries (deps/) wins the search order over
//! System32. Linux and macOS resolve via the `$ORIGIN`/`@loader_path` rpath that
//! sherpa-onnx-sys already emits, so this is a no-op there.

use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");

    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }

    // OUT_DIR = <target>/<profile>/build/stt-agent-<hash>/out
    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("cargo always sets OUT_DIR"));
    let Some(profile_dir) = out_dir.ancestors().nth(3).map(PathBuf::from) else {
        return;
    };
    let deps_dir = profile_dir.join("deps");
    // sherpa-onnx-sys caches its extracted prebuilt archives under <target>/.
    let Some(prebuilt_root) = profile_dir.parent().map(|t| t.join("sherpa-onnx-prebuilt"))
    else {
        return;
    };

    // sherpa-onnx-sys (a dependency) has already run and downloaded the archive by
    // the time this script executes. If the layout ever changes this quietly does
    // nothing — and the loud System32 version-mismatch error comes back, which is
    // itself the signal to revisit this script.
    let Ok(archives) = fs::read_dir(&prebuilt_root) else {
        return;
    };
    for archive in archives.flatten() {
        let lib_dir = archive.path().join("lib");
        let Ok(entries) = fs::read_dir(&lib_dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("dll") {
                continue;
            }
            let Some(name) = path.file_name() else {
                continue;
            };
            if let Err(err) = fs::copy(&path, deps_dir.join(name)) {
                println!(
                    "cargo:warning=could not stage {} into deps/: {err}",
                    path.display()
                );
            }
        }
    }
}
