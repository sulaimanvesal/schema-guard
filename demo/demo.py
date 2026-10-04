"""Zero-API-key demo: guard() rescuing typical broken LLM outputs.

Run:  python demo/demo.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemaguard import guard

# A schema for a structured "book pick" an agent might return.
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "author": {"type": "string"},
        "year": {"type": "integer"},
        "rating": {"type": "number"},
        "genres": {"type": "array", "items": {"type": "string"}},
        "audience": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
        "summary": {"type": "string", "maxLength": 60},
    },
    "required": ["title", "author", "year"],
    "additionalProperties": False,
}

# Five failure modes LLMs produce in the wild.
BROKEN_OUTPUTS = {
    "code fence + prose": (
        'Here you go:\n```json\n{"title": "Project Hail Mary", "author": "Andy Weir", "year": 2021}\n```'
    ),
    "trailing commas + string year": (
        '{"title": "Dune", "author": "Frank Herbert", "year": "1965", "genres": "sci-fi",}'
    ),
    "comments + enum case": (
        '{\n// staff pick\n"title": "Klara and the Sun", "author": "Kazuo Ishiguro",\n'
        '"year": 2021, "audience": "Intermediate", "rating": "4.5"\n}'
    ),
    "long summary + extra field": (
        '{"title": "Piranesi", "author": "Susanna Clarke", "year": 2020, '
        '"summary": "a strange and beautiful labyrinth of a novel that keeps unfolding", '
        '"mood": "dreamlike"}'
    ),
    "missing required field (unfixable)": '{"title": "The Midnight Library"}',
}


def main() -> None:
    print("schema-guard demo — repairing broken LLM outputs\n" + "=" * 55)
    for label, raw in BROKEN_OUTPUTS.items():
        result = guard(raw, SCHEMA)
        print(f"\n### {label}")
        print(f"ok: {result.ok}")
        if result.repairs:
            print("repairs:")
            for action in result.repairs:
                print(f"  - {action}")
        if result.ok:
            print("data:", json.dumps(result.data))
        else:
            print("errors:")
            for err in result.errors:
                print(f"  - {err}")


if __name__ == "__main__":
    main()
