import json
import subprocess
import sys
from pathlib import Path

import pytest

from schemaguard import validate

SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name"],
}


def test_validate_ok():
    report = validate({"name": "Ada", "age": 36}, SCHEMA)
    assert report.valid and report.errors == []


def test_validate_reports_json_pointer_paths():
    report = validate({"age": "not-a-number"}, SCHEMA)
    assert not report.valid
    paths = {e.path for e in report.errors}
    assert "" in paths  # missing required "name" -> root
    assert "/age" in paths
    assert all(str(e) for e in report.errors)  # str() never crashes


def test_validate_rejects_broken_schema():
    with pytest.raises(Exception):
        validate({"a": 1}, {"type": "nonsense-type"})


def test_cli_end_to_end(tmp_path: Path):
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps({"type": "object", "properties": {"n": {"type": "integer"}}}))
    input_file = tmp_path / "out.txt"
    input_file.write_text('```json\n{"n": "42",}\n```')

    proc = subprocess.run(
        [sys.executable, "-m", "schemaguard", "--schema", str(schema_file), "--input", str(input_file)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["data"] == {"n": 42}


def test_cli_fails_on_unfixable(tmp_path: Path):
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps({"type": "object", "required": ["n"]}))
    input_file = tmp_path / "out.txt"
    input_file.write_text('{"m": 1}')

    proc = subprocess.run(
        [sys.executable, "-m", "schemaguard", "--schema", str(schema_file), "--input", str(input_file)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["errors"]
