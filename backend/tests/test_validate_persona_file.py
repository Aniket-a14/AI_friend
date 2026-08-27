"""Persona Guard triggers on `config/persona.toml` but, before this, only
`json.load`d the two JSON seeds -- nothing asserted the TOML users actually
hand-edit even parses, let alone stays in bounds."""

from pathlib import Path

from scripts.validate_persona_file import validate


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "persona.toml"
    path.write_text(text)
    return path


def test_missing_file_is_reported_not_silently_valid(tmp_path):
    problems = validate(tmp_path / "does_not_exist.toml")
    assert problems


def test_malformed_toml_is_reported(tmp_path):
    """`read_persona_file` swallows a parse error and returns {} so a real
    boot degrades to defaults; a validator must turn that same {} back into
    a reported failure instead of a silent pass."""
    path = _write(tmp_path, "this is not = valid [[[ toml")

    problems = validate(path)

    assert problems
    assert any("did not parse" in p for p in problems)


def test_unknown_key_is_reported_by_name(tmp_path):
    """A misspelled field (baseline_valance for baseline_valence) must name
    itself in the failure, or an author has no way to find their typo."""
    path = _write(tmp_path, 'name = "Test"\nbaseline_valance = 0.5\n')

    problems = validate(path)

    assert any("baseline_valance" in p for p in problems)


def test_immutable_key_is_a_hard_failure(tmp_path):
    """strip_immutable only warns and drops these in production, since a
    broken boot is worse than an ignored key -- but a validator run by a
    human or CI should stop them outright."""
    path = _write(tmp_path, 'name = "Test"\nvalues = ["Nope"]\n')

    problems = validate(path)

    assert any("immutable" in p for p in problems)


def test_out_of_bounds_value_is_reported(tmp_path):
    """mood_decay_rate = 0 is the specific failure mode PersonaProfile's
    bounds exist to prevent: zero permanently locks mood at whatever it
    last felt."""
    path = _write(tmp_path, 'name = "Test"\nmood_decay_rate = 0.0\n')

    problems = validate(path)

    assert any("mood_decay_rate" in p for p in problems)


def test_well_formed_file_has_no_problems(tmp_path):
    path = _write(
        tmp_path,
        'name = "Test"\nbaseline_valence = 0.2\ntraits = ["Curious"]\n',
    )

    assert validate(path) == []


def test_the_real_shipped_persona_file_is_valid():
    """The file this whole validator exists to check, checked directly --
    catches config/persona.toml regressing without anyone running CI."""
    repo_root = Path(__file__).resolve().parents[2]
    problems = validate(repo_root / "config" / "persona.toml")
    assert problems == []
