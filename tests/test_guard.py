import pytest

from schemaguard import guard

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "year": {"type": "integer"},
        "rating": {"type": "number"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "genre": {"type": "string", "enum": ["sci-fi", "fantasy", "non-fiction"]},
        "blurb": {"type": "string", "maxLength": 20},
    },
    "required": ["title", "year"],
    "additionalProperties": False,
}


def test_clean_output_passes_untouched():
    raw = '{"title": "Dune", "year": 1965, "genre": "sci-fi"}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data == {"title": "Dune", "year": 1965, "genre": "sci-fi"}
    assert r.repairs == []


def test_code_fence_and_prose_stripped():
    raw = 'Here is the JSON you asked for:\n```json\n{"title": "Dune", "year": 1965}\n```\nHope this helps!'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data["title"] == "Dune"
    assert any("code fence" in a for a in r.repairs)


def test_trailing_commas_removed():
    raw = '{"title": "Dune", "year": 1965,}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data["year"] == 1965


def test_string_year_coerced_to_integer():
    raw = '{"title": "Dune", "year": "1965"}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data["year"] == 1965
    assert isinstance(r.data["year"], int)


def test_float_year_coerced_to_integer():
    raw = '{"title": "Dune", "year": 1965.0}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data["year"] == 1965


def test_enum_matched_case_insensitively():
    raw = '{"title": "Dune", "year": 1965, "genre": "Sci-Fi"}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data["genre"] == "sci-fi"


def test_scalar_wrapped_into_array():
    raw = '{"title": "Dune", "year": 1965, "tags": "classic"}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert r.data["tags"] == ["classic"]


def test_unknown_property_dropped():
    raw = '{"title": "Dune", "year": 1965, "author": "Herbert"}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert "author" not in r.data


def test_string_truncated_to_max_length():
    raw = '{"title": "Dune", "year": 1965, "blurb": "a very very long blurb indeed"}'
    r = guard(raw, SCHEMA)
    assert r.ok
    assert len(r.data["blurb"]) == 20


def test_missing_required_field_is_unfixable():
    raw = '{"title": "Dune"}'
    r = guard(raw, SCHEMA)
    assert not r.ok
    assert any("year" in e.message and e.validator == "required" for e in r.errors)


def test_garbage_text_reports_parse_error():
    r = guard("sorry, I cannot comply with that request", SCHEMA)
    assert not r.ok
    assert r.errors and r.errors[0].validator == "parse"


def test_no_repair_is_strict():
    raw = '```json\n{"title": "Dune", "year": 1965}\n```'
    r = guard(raw, SCHEMA, repair=False)
    assert not r.ok


def test_repair_is_idempotent():
    raw = '{"title": "Dune", "year": "1965", "tags": "classic",}'
    first = guard(raw, SCHEMA)
    assert first.ok
    second = guard(__import__("json").dumps(first.data), SCHEMA)
    assert second.ok
    assert second.repairs == []


def test_raise_for_errors():
    r = guard('{"title": "Dune"}', SCHEMA)
    with pytest.raises(ValueError, match="schema guard"):
        r.raise_for_errors()
