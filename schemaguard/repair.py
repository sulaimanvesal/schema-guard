"""Deterministic repair passes for broken LLM JSON.

Two levels:
  1. text-level — fix the raw string so it parses as JSON.
  2. data-level — fix the parsed value so it validates against the schema.

Every repair is recorded as a human-readable action string, so the caller can
see exactly what was changed (no silent magic).
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
_LINE_COMMENT_RE = re.compile(r"(?m)(?<!:)//[^\n]*$")  # (?<!:) keeps http:// and https:// intact
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_SMART_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})


def _last_balanced(text: str) -> str | None:
    """Return the largest {...} or [...] substring, or None if none found."""
    best: str | None = None
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            if best is None or len(candidate) > len(best):
                best = candidate
    return best


def repair_text(raw: str) -> tuple[str, list[str]]:
    """Apply text-level repairs to ``raw``. Returns (new_text, actions)."""
    actions: list[str] = []
    text = raw

    # 1. Normalize smart quotes (copy-paste from chat UIs).
    if any(c in text for c in "\u201c\u201d\u2018\u2019"):
        text = text.translate(_SMART_QUOTES)
        actions.append("normalized smart quotes to ASCII quotes")

    # 2. Unwrap markdown code fences.
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1)
        actions.append("unwrapped markdown code fence")

    # 3. Strip prose around the JSON payload.
    stripped = _last_balanced(text)
    if stripped is not None and stripped != text.strip():
        text = stripped
        actions.append("stripped surrounding prose, kept JSON payload")

    # 4. Remove JS-style comments LLMs sometimes emit.
    no_comments = _BLOCK_COMMENT_RE.sub("", text)
    no_comments = _LINE_COMMENT_RE.sub("", no_comments)
    if no_comments != text:
        text = no_comments
        actions.append("removed // and /* */ comments")

    # 5. Remove trailing commas: {"a": 1,} -> {"a": 1}.
    no_trailing = _TRAILING_COMMA_RE.sub(r"\1", text)
    if no_trailing != text:
        text = no_trailing
        actions.append("removed trailing commas")

    return text.strip(), actions


# ---------------------------------------------------------------------------
# Data-level repairs
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _coerce_scalar(value: Any, expected: str) -> tuple[Any, bool]:
    """Try to coerce ``value`` to the schema ``expected`` type. Returns (value, changed)."""
    if expected == "string" and not isinstance(value, str):
        if isinstance(value, (int, float, bool)):
            return str(value), True
        return value, False
    if expected == "integer" and isinstance(value, str):
        s = value.strip().replace(",", "")
        if _NUMERIC_RE.match(s):
            num = float(s)
            if num.is_integer():
                return int(num), True
        return value, False
    if expected == "integer" and isinstance(value, float) and value.is_integer():
        return int(value), True
    if expected == "number" and isinstance(value, str):
        s = value.strip().replace(",", "")
        if _NUMERIC_RE.match(s):
            return float(s), True
        return value, False
    if expected == "boolean" and isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "1"):
            return True, True
        if low in ("false", "no", "0"):
            return False, True
        return value, False
    if expected == "null" and isinstance(value, str) and value.strip().lower() in ("null", "none", ""):
        return None, True
    return value, False


def _expected_types(subschema: dict) -> list[str]:
    t = subschema.get("type")
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    if isinstance(t, str):
        return [t]
    return []


def repair_data(data: Any, schema: dict, _path: str = "") -> tuple[Any, list[str]]:
    """Recursively repair ``data`` so it validates against ``schema``.

    Conservative by design: only fixes that are unambiguous —
    type coercion, enum case-insensitivity, defaults, maxLength truncation,
    scalar->single-item-array, and dropping extras when additionalProperties
    is false. Never invents values for missing *required* fields.
    """
    actions: list[str] = []
    where = _path or "<root>"

    # 1. Scalar type coercion.
    for expected in _expected_types(schema):
        coerced, changed = _coerce_scalar(data, expected)
        if changed:
            actions.append(f"{where}: coerced {data!r} to {expected}")
            data = coerced
            break

    # 2. Wrap a bare scalar into a single-item array.
    if "array" in _expected_types(schema) and not isinstance(data, list):
        actions.append(f"{where}: wrapped scalar into single-item array")
        data = [data]

    # 3. Enum: case-insensitive match.
    enum = schema.get("enum")
    if isinstance(enum, list) and isinstance(data, str):
        for choice in enum:
            if isinstance(choice, str) and choice.lower() == data.lower() and choice != data:
                actions.append(f"{where}: matched enum choice {choice!r} (was {data!r})")
                data = choice
                break

    # 4. Recurse into objects.
    if isinstance(data, dict) and schema.get("type") in ("object", None):
        props: dict = schema.get("properties", {})
        # Fill defaults for missing optional properties.
        for name, subschema in props.items():
            if name not in data and "default" in subschema:
                data[name] = subschema["default"]
                actions.append(f"{where}/{name}: filled default {subschema['default']!r}")
        # Drop unknown properties when the schema forbids them.
        if schema.get("additionalProperties") is False:
            for name in list(data.keys()):
                if name not in props:
                    del data[name]
                    actions.append(f"{where}/{name}: dropped unknown property")
        # Recurse into known properties.
        for name, subschema in props.items():
            if name in data:
                data[name], sub_actions = repair_data(data[name], subschema, f"{where}/{name}")
                actions.extend(sub_actions)
        # patternProperties / additionalProperties schemas: apply to extras.
        extra_schema = schema.get("additionalProperties")
        if isinstance(extra_schema, dict):
            for name in data:
                if name not in props:
                    data[name], sub_actions = repair_data(data[name], extra_schema, f"{where}/{name}")
                    actions.extend(sub_actions)

    # 5. Recurse into arrays.
    if isinstance(data, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(data):
                data[i], sub_actions = repair_data(item, item_schema, f"{where}/{i}")
                actions.extend(sub_actions)

    # 6. Truncate strings that exceed maxLength.
    max_len = schema.get("maxLength")
    if isinstance(data, str) and isinstance(max_len, int) and len(data) > max_len:
        data = data[:max_len]
        actions.append(f"{where}: truncated string to maxLength={max_len}")

    return data, actions


def try_parse(text: str) -> tuple[Any, str | None]:
    """Parse JSON, returning (value, None) or (None, error_message)."""
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, str(e)
