"""schema-guard: validate and auto-repair structured LLM outputs against JSON Schema."""

from schemaguard.guard import GuardResult, guard
from schemaguard.validator import ValidationReport, validate
from schemaguard.repair import repair_data, repair_text
from schemaguard.errors import SchemaError

__all__ = [
    "GuardResult",
    "guard",
    "ValidationReport",
    "validate",
    "repair_data",
    "repair_text",
    "SchemaError",
]
__version__ = "0.1.0"
