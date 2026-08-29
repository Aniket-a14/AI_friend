"""CLAUDE.md must not name files that do not exist.

Three times in three days a stale path in a document caused a real problem: the
Persona Guard's `paths:` filter pointed at `backend/persona/**`, so the guard
never ran when the identity seeds changed (#88); `backend/README.md` told
readers to launch Python voice/STT modules that are now Rust binaries (#88); and
CLAUDE.md described cortisol as an open item months after it shipped, which sent
a reader off to build something that already existed (#90).

CLAUDE.md is the highest-leverage instance because it is loaded as instructions
and read in present tense, so a stale claim there is not history -- it is a
wrong answer, delivered with authority, to whoever reads it next.

Only the *mechanical* half is enforced here: a path named in backticks either
resolves or it does not. Prose staleness ("still", "not yet", "open item") is
deliberately **not** asserted -- that judgement needs a human, and a fuzzy check
that cries wolf gets muted, which is how the Persona Guard's markup step came to
be ignored for its whole life.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

# A path named in CLAUDE.md is written relative to whichever directory the
# surrounding prose is talking about; these are the roots that prose uses.
CANDIDATE_ROOTS = (
    REPO_ROOT,
    REPO_ROOT / "backend",
    REPO_ROOT / "backend" / "app",
)

# Bare filenames ("brain_agent.py") are searched for by basename, but only
# inside live source -- `_archive/` holds retired twins of several live modules
# (voice/agent.py most notably), so searching it would let a doc reference
# "resolve" to the very file it was supposed to stop pointing at.
BASENAME_SEARCH_ROOTS = (
    REPO_ROOT / "backend" / "app",
    REPO_ROOT / "backend" / "crates",
    REPO_ROOT / "backend" / "scripts",
)

_PATHISH_SUFFIXES = (".py", ".md", ".json", ".toml", ".yml", ".yaml", ".rs", ".sql")


def _backticked(text: str) -> list[str]:
    return sorted(set(re.findall(r"`([^`\n]+)`", text)))


def _is_pathish(token: str) -> bool:
    if " " in token or token.startswith("$"):
        return False
    stripped = token.rstrip("*/")
    if not stripped:
        return False
    return "/" in token or stripped.endswith(_PATHISH_SUFFIXES)


def _resolves(token: str) -> bool:
    # `cognitive/**` and `app/` both denote a directory; compare on the stem.
    stem = token.rstrip("*").rstrip("/")
    if not stem:
        return False

    if "/" in stem:
        return any((root / stem).exists() for root in CANDIDATE_ROOTS)

    if any((root / stem).exists() for root in CANDIDATE_ROOTS):
        return True
    return any(any(root.rglob(stem)) for root in BASENAME_SEARCH_ROOTS if root.exists())


def test_claude_md_exists():
    """Everything below is vacuously true if the file moved."""
    assert CLAUDE_MD.is_file(), f"CLAUDE.md not found at {CLAUDE_MD}"


def test_every_path_named_in_claude_md_exists():
    """A path in CLAUDE.md that does not resolve is a wrong answer to whoever
    reads it next -- and, when the same string is also a CI `paths:` filter, a
    silently disabled workflow.

    Reports every broken reference at once: fixing stale docs one failure per
    run is how they stay stale.
    """
    tokens = [
        token
        for token in _backticked(CLAUDE_MD.read_text(encoding="utf-8"))
        if _is_pathish(token)
    ]

    # If the extractor stops matching anything, this test would pass while
    # checking nothing -- the always-green failure mode this repo has now hit
    # twice (the Persona Guard seed glob, and an empty eval `Check`).
    assert len(tokens) >= 20, (
        f"only {len(tokens)} path-shaped tokens found in CLAUDE.md; the "
        "extractor is probably broken rather than the document being short"
    )

    missing = [token for token in tokens if not _resolves(token)]
    assert not missing, "CLAUDE.md names paths that do not exist: " + ", ".join(
        repr(token) for token in missing
    )


@pytest.mark.parametrize(
    "token,expected",
    [
        ("backend/app/contracts.py", True),
        ("cognitive/**", True),  # glob -> directory stem
        ("app/", True),  # trailing slash
        ("brain_agent.py", True),  # bare filename, found by search
        ("voice/agent.py", False),  # archived; must NOT resolve
        ("prosody.py", False),  # archived twin; must NOT resolve
        ("state/no_such_module.py", False),
    ],
)
def test_the_resolver_distinguishes_live_paths_from_archived_ones(token, expected):
    """The resolver is the whole test; if it answered True for everything the
    check above would pass on any document.

    `voice/agent.py` and `prosody.py` are the load-bearing cases: both exist
    under `_archive/`, and both are exactly the kind of reference that has
    already shipped in docs. A basename search that reached into `_archive`
    would confirm the stale path instead of catching it.
    """
    assert _resolves(token) is expected
