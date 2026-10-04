"""Main entry point: guard() — parse, repair, and validate an LLM output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schemaguard.errors import SchemaError
from schemaguard.repair import repair_data, repair_text, try_parse
from schemaguard.validator import validate


@dataclass
class GuardResult:
    """Outcome of guarding one raw LLM output against a schema."""

    ok: bool
    data: Any = None
    repairs: list[str] = field(default_factory=list)
    errors: list[SchemaError] = field(default_factory=list)

    def raise_for_errors(self) -> "GuardResult":
        """Raise ValueError with a readable summary if the output is unusable."""
        if not self.ok:
            detail = "; ".join(str(e) for e in self.errors)
            raise ValueError(f"LLM output failed schema guard: {detail}")
        return self

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "data": self.data,
            "repairs": self.repairs,
            "errors": [{"path": e.path, "message": e.message, "validator": e.validator} for e in self.errors],
        }


def guard(raw: str, schema: dict, *, repair: bool = True, max_passes: int = 3) -> GuardResult:
    """Validate a raw LLM text output against a JSON Schema.

    Pipeline: text repair -> JSON parse -> data repair -> validate, iterated
    until the output validates or no repair makes progress. With
    ``repair=False`` this is a strict validator that reports parse failures
    and schema errors without touching anything.
    """
    repairs: list[str] = []
    text = raw

    # --- text repair + parse loop -----------------------------------------
    data: Any = None
    parse_error: str | None = None
    for _ in range(max_passes + 1):
        data, parse_error = try_parse(text)
        if parse_error is None:
            break
        if not repair:
            break
        new_text, actions = repair_text(text)
        if not actions or new_text == text:
            break
        repairs.extend(actions)
        text = new_text

    if parse_error is not None:
        return GuardResult(
            ok=False,
            repairs=repairs,
            errors=[SchemaError(path="", message=f"not valid JSON: {parse_error}", validator="parse")],
        )

    # --- data repair + validate loop --------------------------------------
    report = validate(data, schema)
    if repair:
        for _ in range(max_passes):
            if report.valid:
                break
            new_data, actions = repair_data(report.data, schema)
            if not actions:
                break
            repairs.extend(actions)
            report = validate(new_data, schema)

    return GuardResult(ok=report.valid, data=report.data, repairs=repairs, errors=report.errors)
