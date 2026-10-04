"""Schema validation that returns normalized, human-readable errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JsonSchemaError

from schemaguard.errors import SchemaError


@dataclass
class ValidationReport:
    valid: bool
    errors: list[SchemaError] = field(default_factory=list)
    data: Any = None


def validate(data: Any, schema: dict) -> ValidationReport:
    """Validate ``data`` against ``schema``; never raises on bad *data*.

    Raises jsonschema.exceptions.SchemaError if the *schema* itself is invalid —
    that's a programmer bug, not an LLM output problem.
    """
    validator = Draft202012Validator(schema)
    # Fail fast on a broken schema so it surfaces during development, not in prod.
    validator.check_schema(schema)

    errors: list[SchemaError] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        parts = [str(p).replace("~", "~0").replace("/", "~1") for p in err.absolute_path]
        pointer = "/" + "/".join(parts) if parts else ""  # RFC 6901: root is ""
        errors.append(
            SchemaError(
                path=pointer,
                message=err.message,
                validator=err.validator or "unknown",
            )
        )
    return ValidationReport(valid=not errors, errors=errors, data=data)


def is_valid(data: Any, schema: dict) -> bool:
    """Convenience boolean check."""
    return validate(data, schema).valid
