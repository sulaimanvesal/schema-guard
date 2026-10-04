from schemaguard import repair_data, repair_text
from schemaguard.repair import try_parse


def test_repair_text_unwraps_fence_and_strips_prose():
    raw = 'Sure!\n```json\n{"a": 1,}\n```\nDone.'
    text, actions = repair_text(raw)
    assert text == '{"a": 1}'
    assert len(actions) >= 2
    parsed, err = try_parse(text)
    assert err is None and parsed == {"a": 1}


def test_repair_text_normalizes_smart_quotes():
    raw = '{"a": \u201chello\u201d}'
    text, _ = repair_text(raw)
    parsed, err = try_parse(text)
    assert err is None and parsed == {"a": "hello"}


def test_repair_text_removes_comments():
    raw = '{\n// a comment\n"a": 1 /* inline */\n}'
    text, _ = repair_text(raw)
    parsed, err = try_parse(text)
    assert err is None and parsed == {"a": 1}


def test_repair_data_coerces_nested_values():
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"price": {"type": "number"}},
                },
            }
        },
    }
    data = {"items": [{"price": "19.99"}]}
    fixed, actions = repair_data(data, schema)
    assert fixed == {"items": [{"price": 19.99}]}
    assert actions


def test_repair_data_fills_defaults():
    schema = {
        "type": "object",
        "properties": {
            "retries": {"type": "integer", "default": 3},
            "name": {"type": "string"},
        },
    }
    fixed, actions = repair_data({"name": "x"}, schema)
    assert fixed["retries"] == 3
    assert any("default" in a for a in actions)


def test_repair_data_coerces_booleans():
    schema = {"type": "object", "properties": {"flag": {"type": "boolean"}}}
    fixed, _ = repair_data({"flag": "yes"}, schema)
    assert fixed["flag"] is True
    fixed, _ = repair_data({"flag": "False"}, schema)
    assert fixed["flag"] is False


def test_repair_data_does_not_invent_required_values():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }
    fixed, _ = repair_data({}, schema)
    assert "a" not in fixed
