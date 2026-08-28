# Changelog

All notable changes to this project are documented in this file, starting
from v7.0.0. Tagged releases exist back to v2.0.0; the gap before v7.0.0 was
this file simply never being kept in sync with the release history that
GitHub Releases and `git tag` already record — see those for the raw list of
prior tags.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
from this entry onward.

For the real, detailed, dated development history — including what was
measured, what was deliberately left undone, and why — see
[`.agents/CONTEXT.md`](.agents/CONTEXT.md), the project's engineering ledger.
It is the source of truth; where any other document in this repo disagrees
with it, the ledger is right.

## v7.0.0

The community-release roadmap (`.agents/CONTEXT.md`, "Community roadmap
Phase 0" through "Phase 8"): ground-truth fixes to the safety floor and
persona validation, a fresh clone that boots and speaks, the `friend`
persona/voice creation flow, proactive outreach and affect persistence
across restarts, export/import portability, a real web UI, the nine
pressure-test benchmark scenarios run for real, code-quality gates flipped
from report-only to blocking, and a rewritten README and landing page.

On top of that roadmap, this release adds the distribution system: one-line
installers for macOS/Linux (`scripts/install.sh`) and Windows
(`scripts/install.ps1`), a lightweight standalone runtime bundle (~4.3 MB,
`scripts/package_release.py`), the unified `friend` CLI
(`scripts/friend_cli.py`) covering init/start/stop/status/model/vision/talk/
persona/voice/backup/logs/update, an interactive `friend init` environment
wizard that generates cryptographically secure credentials, and Moondream
VLM visual appraisal wired into setup and the CLI.

Fixed as part of preparing this release: `personal/` was briefly
whitelisted into the packaged runtime bundle and shipped the maintainer's
own persona data publicly; the packager no longer includes it and a new
`.distignore` guards against it recurring. `friend_cli.py` failed to parse
at all on Python 3.11 despite both installers accepting 3.11 as meeting
their stated minimum. `install.ps1` previously always cloned the full
monorepo and skipped the setup wizard; it now matches the macOS/Linux
installer's lightweight-bundle and interactive-wizard behavior.
