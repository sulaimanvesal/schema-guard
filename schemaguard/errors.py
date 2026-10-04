"""Normalized validation error representation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaError:
    """A single schema validation failure, with a JSON-pointer path."""

    path: str  # e.g. "/items/0/price" — "" means the document root
    message: str
    validator: str  # jsonschema keyword that failed, e.g. "required", "type"

    def __str__(self) -> str:
        where = self.path or "<root>"
        return f"{where}: {self.message} [{self.validator}]"
