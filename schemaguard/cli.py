"""Command line interface: validate (and repair) an LLM output file against a schema.

Usage:
    python -m schemaguard --schema schema.json --input output.txt
    cat output.txt | python -m schemaguard --schema schema.json
"""

from __future__ import annotations

import argparse
import json
import sys

from schemaguard.guard import guard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="schemaguard",
        description="Validate and auto-repair structured LLM outputs against a JSON Schema.",
    )
    parser.add_argument("--schema", required=True, help="Path to the JSON Schema file.")
    parser.add_argument(
        "--input",
        default="-",
        help="Path to the raw LLM output file, or - for stdin (default).",
    )
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="Strict mode: validate only, do not attempt repairs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the repaired JSON on success (useful in pipelines).",
    )
    args = parser.parse_args(argv)

    with open(args.schema, encoding="utf-8") as f:
        schema = json.load(f)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        with open(args.input, encoding="utf-8") as f:
            raw = f.read()

    result = guard(raw, schema, repair=not args.no_repair)

    if args.quiet:
        if result.ok:
            print(json.dumps(result.data, indent=2))
            return 0
        print(json.dumps(result.to_dict(), indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
