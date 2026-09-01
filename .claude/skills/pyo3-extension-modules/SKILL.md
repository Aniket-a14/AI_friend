---
name: pyo3-extension-modules
description: PyO3 extension-module build gotchas -- the extension-module feature trap that breaks `cargo test`, maturin/pyproject.toml feature wiring, abi3 stable-ABI builds, and the try/except-with-pure-Python-fallback pattern for making a Rust accelerator optional. Use when touching a pyo3-based crate (this repo: cognitive-rust), its Cargo.toml/pyproject.toml, a maturin build step, or a Python module that imports a compiled Rust extension.
---

# PyO3 extension modules

Written from a real incident in this repo (`cognitive-rust`, 2026-09-01): a workspace-wide
`pyo3` dependency spec silently broke `cargo test --workspace` for months, worked around with a
two-invocation CI split that misdiagnosed the cause, before being found and fixed at the root.

## The core trap: `extension-module` must not be on for `cargo test`

`pyo3`'s `extension-module` feature tells the linker: *this `.so`/`.dylib` will be loaded into
an already-running Python process, so don't link against libpython -- the symbols are already
present in the host process.* That assumption is true for the real wheel `maturin` builds. It is
**never** true for a standalone `cargo test`/`cargo check` binary, which is not loaded into
Python at all and genuinely needs those symbols resolved at link time.

**Symptom:** a link error naming Python C-API symbols --
`Py_IsInitialized`, `Py_FalseStruct`, `Py_TrueStruct`, `Py_NoneStruct`, or similar --
with `ld: symbol(s) not found for architecture <arch>` / `undefined reference to`. This is not a
missing-dependency problem; it is `extension-module` being enabled somewhere it shouldn't be.

**Where the feature actually gets enabled without anyone asking for it:** Cargo feature
unification. If a workspace-shared dependency spec writes
`pyo3 = { version = "...", features = ["extension-module", ...] }`, *every* consumer of that
shared entry builds with the feature on -- including `cargo test`, `cargo check`, and any other
crate in the workspace that happens to depend on the same pyo3 entry, even one that has nothing
to do with Python. A single `[features]` block or `--features` flag on the actual pyo3-using
crate does not fix this if the feature is already baked into the shared/default spec upstream --
the shared spec is the actual place to fix.

## The fix: opt-in feature, requested only by the real build

1. **Do not put `extension-module` in the shared/workspace dependency spec.** Leave it with
   only the ABI feature (e.g. `abi3-py39`):
   ```toml
   # workspace Cargo.toml
   pyo3 = { version = "0.28", features = ["abi3-py39"] }
   ```
2. **Add it as an opt-in feature on the crate that actually builds the extension:**
   ```toml
   # crates/your-extension/Cargo.toml
   [features]
   extension-module = ["pyo3/extension-module"]
   ```
   Now `cargo test`/`cargo check` at the workspace level never enables it, and link cleanly.
3. **Tell `maturin` to request the feature for the real build.** `maturin build` does not
   automatically enable a non-default feature just because the crate is a `cdylib` with pyo3 --
   it has to be told. Two ways:
   - `maturin build --features extension-module` on the command line, or
   - a `[tool.maturin]` table in `pyproject.toml`:
     ```toml
     [tool.maturin]
     features = ["extension-module"]
     ```
   **Gotcha, confirmed the hard way in this repo:** `maturin` reads whichever `pyproject.toml`
   sits in the *invoking* working directory, regardless of what `--manifest-path` points at. If
   your build command is `cd backend && maturin build --manifest-path crates/foo/Cargo.toml`,
   the config that matters is `backend/pyproject.toml`, not one sitting next to `Cargo.toml`.
   This repo learned this twice: once when removing that table broke five CI jobs (missing
   `[build-system]`), and again when adding `[tool.maturin] features` here was what made every
   existing `maturin build --manifest-path ...` call world-wide pick up the fix with zero
   call-site edits.

## Verify both directions, not just the one you changed

A fix to make `cargo test` pass can silently break the real wheel if the feature wiring is
wrong. Check both, every time:

```bash
cargo test --workspace                       # must pass with NO split/workaround
maturin build --manifest-path crates/foo/Cargo.toml --out target/wheels
# maturin's own log line proves it read the config, don't just trust silence:
#   "Using build options features from pyproject.toml"
pip install target/wheels/*.whl
python -c "import your_extension; print(your_extension.some_expected_function)"
```
If the extension is architecture-specific (a Mac-built wheel is `arm64`, a Linux deployment box
is usually `x86_64`), build **on** the target host -- never copy a wheel across architectures.

## The optional-accelerator pattern (making the extension non-mandatory)

A pyo3 extension used for hot-path acceleration (numeric scoring, decay math, graph algorithms)
should degrade gracefully when not installed, not crash the importing module:

```python
try:
    import your_extension
    result = your_extension.fast_path(args)
except ImportError:
    result = pure_python_equivalent(args)  # must be numerically identical
```

Two disciplines that make this safe long-term:
- **Never** `import your_extension` unconditionally at module level in a file that must import
  cleanly without the compiled artifact present (dev machines that skip the Rust toolchain,
  CI jobs that don't build it, a host where the wheel was never installed). Reserve the
  unconditional form only for entry points that are known-optional/not-currently-deployed.
- **Prove the two paths agree.** A dedicated test asserting the Rust and Python implementations
  produce bit-identical (or tolerance-bounded) output for the same input is what makes it safe
  to silently fall back -- without it, "falls back to Python" can quietly mean "falls back to a
  *different* answer." Write this test once per accelerated function, not once per accelerator.

## Don't assume the extension is installed just because the source builds

Building the crate and installing the wheel are two separate steps on two separate hosts in a
multi-machine deployment (dev laptop vs. a GPU box, say). `cargo test --workspace` passing
proves the *source* links; it says nothing about whether `pip show your_extension` succeeds on
any particular deployment target. Check both independently when debugging "it works on my
machine" for a pyo3-backed feature.
