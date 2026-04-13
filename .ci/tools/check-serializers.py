#!/usr/bin/env python3
"""Serializer completeness checker.

Compares the keys emitted by _serialize_*() functions against the
OpenAPI schema definitions in docs.py. Reports fields that exist
in the schema but are missing from the serializer (data loss risk)
and fields in the serializer but missing from the schema (undocumented).

Usage:
    python3 .ci/tools/check-serializers.py
    python3 .ci/tools/check-serializers.py --json  # machine-readable output
"""
import ast
import argparse
import json
import re
import sys
from pathlib import Path

API_DIR = Path("apps/backend/http-api/src/api/v2")
DOCS_FILE = API_DIR / "docs.py"


def snake_to_pascal(name: str) -> str:
    """Convert _serialize_product -> Product."""
    name = name.replace("_serialize_", "")
    return "".join(w.capitalize() for w in name.split("_"))


def extract_serializer_keys(filepath: Path) -> dict[str, set[str]]:
    """Extract dict literal keys from _serialize_*() functions via AST."""
    serializers: dict[str, set[str]] = {}
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return serializers

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith("_serialize_"):
            continue

        keys: set[str] = set()
        for child in ast.walk(node):
            # Dict literals: {"key": value, ...}
            if isinstance(child, ast.Dict):
                for k in child.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
            # Subscript assignments: data["key"] = value
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if (isinstance(target, ast.Subscript)
                            and isinstance(target.slice, ast.Constant)
                            and isinstance(target.slice.value, str)):
                        keys.add(target.slice.value)

        if keys:
            serializers[node.name] = keys

    return serializers


def extract_schema_properties(filepath: Path) -> dict[str, set[str]]:
    """Extract OpenAPI schema property keys from docs.py via regex."""
    schemas: dict[str, set[str]] = {}
    content = filepath.read_text()

    # Match: spec.components.schema("Name", { ... })
    # We parse the dict argument to extract property names
    pattern = r'spec\.components\.schema\(\s*"(\w+)"'
    for match in re.finditer(pattern, content):
        schema_name = match.group(1)
        # Find the properties dict that follows
        start = match.end()
        # Look for "properties": { ... }
        prop_match = re.search(r'"properties"\s*:\s*\{', content[start:start + 2000])
        if not prop_match:
            continue

        # Extract property keys (top-level only)
        prop_start = start + prop_match.end()
        props: set[str] = set()
        depth = 1
        i = prop_start
        current_key = ""

        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            elif ch == '"' and depth == 1:
                # Extract key at depth 1
                end_quote = content.index('"', i + 1)
                key = content[i + 1:end_quote]
                # Check if followed by : (it's a property key)
                rest = content[end_quote + 1:end_quote + 5].strip()
                if rest.startswith(":"):
                    props.add(key)
                i = end_quote
            i += 1

        if props:
            schemas[schema_name] = props

    return schemas


def compare(serializers: dict[str, set[str]], schemas: dict[str, set[str]]) -> list[dict]:
    """Compare serializer keys against schema properties."""
    findings = []

    for func_name, ser_keys in serializers.items():
        schema_name = snake_to_pascal(func_name)
        if schema_name not in schemas:
            continue  # No matching schema — skip

        schema_keys = schemas[schema_name]

        missing = schema_keys - ser_keys
        extra = ser_keys - schema_keys

        if missing:
            findings.append({
                "serializer": func_name,
                "schema": schema_name,
                "severity": "high" if len(missing) > 3 else "medium",
                "type": "missing",
                "fields": sorted(missing),
                "message": f"{func_name} is missing {len(missing)} field(s) from OpenAPI schema {schema_name}: {', '.join(sorted(missing))}",
            })

        if extra:
            findings.append({
                "serializer": func_name,
                "schema": schema_name,
                "severity": "low",
                "type": "undocumented",
                "fields": sorted(extra),
                "message": f"{func_name} emits {len(extra)} undocumented field(s) not in schema {schema_name}: {', '.join(sorted(extra))}",
            })

    return findings


def main():
    parser = argparse.ArgumentParser(description="Serializer completeness checker")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # Collect all serializers
    all_serializers: dict[str, set[str]] = {}
    for py_file in API_DIR.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        all_serializers.update(extract_serializer_keys(py_file))

    # Collect all schemas
    if not DOCS_FILE.exists():
        print(f"ERROR: {DOCS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    all_schemas = extract_schema_properties(DOCS_FILE)

    # Compare
    findings = compare(all_serializers, all_schemas)

    if args.json:
        print(json.dumps({
            "serializers_found": len(all_serializers),
            "schemas_found": len(all_schemas),
            "findings": findings,
        }, indent=2))
    else:
        print(f"Serializers found: {len(all_serializers)}")
        print(f"Schemas found:     {len(all_schemas)}")
        print(f"Findings:          {len(findings)}")
        print()
        for f in findings:
            icon = "!!" if f["severity"] in ("high", "critical") else "  "
            print(f'{icon} [{f["severity"]}] {f["message"]}')
        print()

    if any(f["severity"] in ("high", "critical") for f in findings):
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
