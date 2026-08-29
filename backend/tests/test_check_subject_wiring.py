"""
P1-8: the subject-wiring checker (scripts/check_subject_wiring.py) is CI
enforcement, so it needs to prove it actually catches the defect class it
exists for - a fixture with a one-ended subject must fail it, per
`ROADMAP.md`'s own requirement for this item ("the check tests itself").
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_subject_wiring as wiring


def test_the_real_repository_passes_clean():
    """Regression guard: if this starts failing, either a real wiring
    defect was introduced, or something the checker doesn't yet know about
    needs an ALLOWLIST entry - not the check silently going warn-only."""
    assert wiring.main() == 0


@pytest.fixture
def fixture_repo(tmp_path, monkeypatch):
    """A minimal synthetic repo tree with a known one-ended subject, so the
    checker's logic can be exercised in isolation from the real codebase."""
    backend_root = tmp_path
    app_root = backend_root / "app"
    crates_root = backend_root / "crates"
    app_root.mkdir()
    crates_root.mkdir()

    (app_root / "contracts.py").write_text(
        "from enum import Enum\n\n\n"
        "class Topics(str, Enum):\n"
        '    ONE_ENDED = "test.one_ended"\n'
        '    WELL_WIRED = "test.well_wired"\n'
    )
    (app_root / "nats_streams.py").write_text(
        'CORE_STREAMS: dict = {\n    "TEST_STREAM": ["test.>"],\n}\n'
    )
    (crates_root / "contracts").mkdir()
    (crates_root / "contracts" / "src").mkdir(parents=True)
    (crates_root / "contracts" / "src" / "lib.rs").write_text("pub mod topics {}\n")

    agent_file = app_root / "some_agent.py"
    agent_file.write_text(
        "from .contracts import Topics\n\n\n"
        "async def run(agent):\n"
        "    # ONE_ENDED is published but nothing ever subscribes to it.\n"
        "    await agent.publish(Topics.ONE_ENDED, {})\n"
        "    await agent.subscribe(Topics.WELL_WIRED, handler)\n"
    )
    another_file = app_root / "another_agent.py"
    another_file.write_text(
        "from .contracts import Topics\n\n\n"
        "async def run(agent):\n"
        "    await agent.publish(Topics.WELL_WIRED, {})\n"
    )

    monkeypatch.setattr(wiring, "BACKEND_ROOT", backend_root)
    monkeypatch.setattr(wiring, "APP_ROOT", app_root)
    monkeypatch.setattr(wiring, "CRATES_ROOT", crates_root)
    monkeypatch.setattr(wiring, "CONTRACTS_PY", app_root / "contracts.py")
    monkeypatch.setattr(wiring, "NATS_STREAMS_PY", app_root / "nats_streams.py")
    monkeypatch.setattr(
        wiring, "CONTRACTS_RS", crates_root / "contracts" / "src" / "lib.rs"
    )
    monkeypatch.setattr(wiring, "TRANSPORT_IMPL_FILES", set())
    monkeypatch.setattr(wiring, "ALLOWLIST", {})

    return backend_root


def test_fixture_with_one_ended_subject_fails(fixture_repo, capsys):
    """The check's core purpose: a subject published but never subscribed
    (or vice versa) must fail the build, not just get logged."""
    exit_code = wiring.main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "test.one_ended" in captured.out
    assert "published but never subscribed" in captured.out


def test_fixture_well_wired_subject_does_not_fail(fixture_repo, capsys):
    """The inverse guard: a subject with both ends wired must NOT appear in
    the failure output - otherwise the check would be trivially useless
    (failing on everything, including correct wiring)."""
    wiring.main()

    captured = capsys.readouterr()
    unallowlisted_section = captured.out.split("UNALLOWLISTED")[-1]
    assert "test.well_wired" not in unallowlisted_section


def test_allowlisted_issue_does_not_fail_the_build(fixture_repo, monkeypatch, capsys):
    """An allowlisted subject still gets reported (for visibility) but must
    not fail the build - that is the whole point of the allowlist letting
    this check land enforcing rather than warn-only."""
    monkeypatch.setattr(
        wiring,
        "ALLOWLIST",
        {"test.one_ended": "deliberately allowlisted for this test"},
    )

    exit_code = wiring.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "test.one_ended" in captured.out
    assert "allowlisted: deliberately allowlisted for this test" in captured.out
