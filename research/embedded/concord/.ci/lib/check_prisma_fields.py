#!/usr/bin/env python3
"""Prisma field static analyzer — advisory mode (v1).

Parses prisma/schema.prisma to extract model field registries, then
grep-walks Python source files for ``db.<model>.create(`` call sites and
checks whether the dict keys in ``data={...}`` are valid scalar fields on
that model.

This is an ADVISORY tool — it exits 0 regardless of warnings so it never
blocks CI. Once field coverage stabilizes the exit code can be tightened.

Usage::

    python3 .ci/lib/check_prisma_fields.py apps/backend/http-api/src/
    python3 .ci/lib/check_prisma_fields.py apps/backend/http-api/src/ --strict

Exit codes:
    0  — clean (or advisory mode: always 0)
    1  — strict mode: unknown fields found
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, NamedTuple, Set


# ---------------------------------------------------------------------------
# Prisma schema parser
# ---------------------------------------------------------------------------

#: Prisma scalar types recognised as non-relation fields.
_SCALAR_TYPES = {
    "String", "Int", "Float", "BigInt", "Boolean", "DateTime",
    "Json", "Bytes", "Decimal",
}

#: Lines inside model blocks that are metadata or empty — skip them.
_SKIP_PATTERNS = re.compile(r"^\s*(?:@@|//|$)")

#: Field line: ``fieldName  TypeOrRelation  modifiers...``
_FIELD_PATTERN = re.compile(r"^\s*(\w+)\s+(\w+)(\??)((\[\])?)")


class ModelInfo(NamedTuple):
    scalar_fields: Set[str]   # fields that can appear in create/update data
    relation_fields: Set[str]  # relation fields (should NOT appear in create data)


def parse_schema(schema_path: Path) -> Dict[str, ModelInfo]:
    """Parse a Prisma schema and return a registry of model → fields."""
    text = schema_path.read_text(encoding="utf-8")
    models: Dict[str, ModelInfo] = {}

    inside_model = False
    current_model: str = ""
    scalar: Set[str] = set()
    relation: Set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Enter a model block
        if not inside_model:
            m = re.match(r"^model\s+(\w+)\s*\{", line)
            if m:
                inside_model = True
                current_model = m.group(1)
                scalar = set()
                relation = set()
            continue

        # Exit model block
        if line == "}":
            models[current_model.lower()] = ModelInfo(
                scalar_fields=frozenset(scalar),
                relation_fields=frozenset(relation),
            )
            inside_model = False
            current_model = ""
            continue

        # Skip metadata lines, directives, and blank lines
        if _SKIP_PATTERNS.match(line):
            continue

        m = _FIELD_PATTERN.match(line)
        if not m:
            continue

        field_name = m.group(1)
        field_type = m.group(2)
        is_array = bool(m.group(5))  # e.g. Board[]

        # Skip Prisma directives that appear as identifiers in some formats
        if field_name in ("model", "enum", "generator", "datasource"):
            continue

        if field_type in _SCALAR_TYPES or field_type.startswith("@"):
            scalar.add(field_name)
        elif field_type[0].isupper() and field_type not in _SCALAR_TYPES:
            # Capitalised type = relation model
            relation.add(field_name)
        else:
            # Enum values (lowercase start) — treated as scalar
            scalar.add(field_name)

    return models


# ---------------------------------------------------------------------------
# Python AST walker — find db.<model>.create(data={...})
# ---------------------------------------------------------------------------

class CreateCallViolation(NamedTuple):
    file: str
    line: int
    model: str
    unknown_fields: Set[str]


def _extract_data_keys_from_dict(node: ast.expr) -> Set[str]:
    """Extract string keys from a dict literal node."""
    keys: Set[str] = set()
    if not isinstance(node, ast.Dict):
        return keys
    for k in node.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.add(k.value)
        elif isinstance(k, ast.Name):
            keys.add(k.id)
    return keys


def _walk_file(
    path: Path,
    models: Dict[str, ModelInfo],
) -> list[CreateCallViolation]:
    """Walk a Python file's AST for db.<model>.create(data={...}) patterns."""
    violations: list[CreateCallViolation] = []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        # Match: db.<model>.create(...)  or  db.<model>.update(...)
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in ("create", "update", "upsert"):
            continue

        # func.value must be  db.<model>  →  Attribute(value=Name(id="db"), attr=<model>)
        # or some alias like  appPostgresClient.<model>
        inner = func.value
        if not isinstance(inner, ast.Attribute):
            continue

        model_name = inner.attr.lower()
        if model_name not in models:
            continue

        model_info = models[model_name]

        # Find the ``data`` keyword argument
        for kw in node.keywords:
            if kw.arg != "data":
                continue

            data_node = kw.value

            # Handle upsert: data={"create": {...}, "update": {...}}
            if isinstance(data_node, ast.Dict):
                # Flat dict — check keys directly
                keys = _extract_data_keys_from_dict(data_node)
                unknown = keys - model_info.scalar_fields - {"id"}
                # Remove Prisma nested write keywords
                unknown -= {"create", "update", "connect", "disconnect", "upsert",
                            "connectOrCreate", "set", "createMany", "updateMany",
                            "deleteMany", "delete"}
                # Remove relation field names (they ARE allowed in nested writes)
                unknown -= model_info.relation_fields
                if unknown:
                    violations.append(CreateCallViolation(
                        file=str(path),
                        line=node.lineno,
                        model=model_name,
                        unknown_fields=unknown,
                    ))

    return violations


def analyze(src_dir: Path, models: Dict[str, ModelInfo]) -> list[CreateCallViolation]:
    """Analyze all Python files under src_dir."""
    all_violations: list[CreateCallViolation] = []
    for py_file in sorted(src_dir.rglob("*.py")):
        all_violations.extend(_walk_file(py_file, models))
    return all_violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src_dir", help="Python source directory to analyze")
    parser.add_argument(
        "--schema",
        default="prisma/schema.prisma",
        help="Path to schema.prisma (relative to repo root)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Exit 1 if unknown fields are found (default: advisory, always exit 0)",
    )
    args = parser.parse_args()

    # Locate prisma schema — try relative to repo root or CWD
    repo_root = Path(__file__).parent.parent.parent  # .ci/lib/ → repo root
    schema_path = repo_root / args.schema
    if not schema_path.exists():
        schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"warn  schema not found at {schema_path} — skipping field analysis")
        return 0

    src_dir = Path(args.src_dir)
    if not src_dir.exists():
        print(f"err   src_dir not found: {src_dir}")
        return 1

    print(f"info  parsing schema: {schema_path}")
    models = parse_schema(schema_path)
    print(f"info  found {len(models)} models: {', '.join(sorted(models.keys()))}")

    print(f"info  analyzing: {src_dir}")
    violations = analyze(src_dir, models)

    if not violations:
        print("ok    no unknown Prisma fields found")
        return 0

    print(f"\nwarn  {len(violations)} potential field issue(s) found:\n")
    for v in violations:
        print(f"  {v.file}:{v.line}")
        print(f"    model={v.model!r}  unknown fields: {sorted(v.unknown_fields)}")
    print()

    if args.strict:
        print("err   strict mode — unknown fields are not allowed")
        return 1

    print("info  advisory mode — not blocking CI (run with --strict to enforce)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
