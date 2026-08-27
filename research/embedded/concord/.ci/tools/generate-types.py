#!/usr/bin/env python3
"""Generate TypeScript interfaces from OpenAPI schema definitions.

Parses the OpenAPI spec components.schemas from docs.py and generates
TypeScript interface declarations. Does not require a running server —
extracts schema definitions via AST/regex from the source file.

Usage:
    python3 .ci/tools/generate-types.py
    python3 .ci/tools/generate-types.py --output /tmp/generated-api.ts
"""
import argparse
import json
import re
import sys
from pathlib import Path

DOCS_FILE = Path("apps/backend/http-api/src/api/v2/docs.py")


def extract_schemas_from_source(filepath: Path) -> dict[str, dict]:
    """Extract OpenAPI schema definitions from docs.py source code.

    Parses spec.components.schema("Name", { ... }) calls by finding
    balanced braces after each call.
    """
    content = filepath.read_text()
    schemas: dict[str, dict] = {}

    # Find all schema registration calls
    pattern = r'spec\.components\.schema\(\s*"(\w+)"\s*,\s*'
    for match in re.finditer(pattern, content):
        name = match.group(1)
        start = match.end()

        # Find the balanced dict literal
        depth = 0
        i = start
        dict_start = -1

        while i < len(content):
            if content[i] == '{':
                if depth == 0:
                    dict_start = i
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    dict_str = content[dict_start:i + 1]
                    # Try to parse as Python dict -> JSON
                    try:
                        # Convert Python dict syntax to JSON
                        json_str = dict_str
                        json_str = json_str.replace("True", "true")
                        json_str = json_str.replace("False", "false")
                        json_str = json_str.replace("None", "null")
                        # Handle trailing commas
                        json_str = re.sub(r',\s*}', '}', json_str)
                        json_str = re.sub(r',\s*]', ']', json_str)
                        schema = json.loads(json_str)
                        schemas[name] = schema
                    except json.JSONDecodeError:
                        pass  # Skip unparseable schemas
                    break
            i += 1

    return schemas


def openapi_type_to_ts(prop: dict, schemas: dict[str, dict]) -> str:
    """Convert an OpenAPI property type to TypeScript."""
    if "$ref" in prop:
        ref_name = prop["$ref"].split("/")[-1]
        return ref_name

    prop_type = prop.get("type", "any")
    nullable = prop.get("nullable", False)
    ts_type = "any"

    if prop_type == "string":
        enum_values = prop.get("enum")
        if enum_values:
            ts_type = " | ".join(f"'{v}'" for v in enum_values)
        elif prop.get("format") == "date-time":
            ts_type = "string"
        else:
            ts_type = "string"
    elif prop_type == "integer" or prop_type == "number":
        ts_type = "number"
    elif prop_type == "boolean":
        ts_type = "boolean"
    elif prop_type == "array":
        items = prop.get("items", {})
        item_type = openapi_type_to_ts(items, schemas)
        ts_type = f"{item_type}[]"
    elif prop_type == "object":
        # Check for additionalProperties (Record type)
        if "additionalProperties" in prop:
            val_type = openapi_type_to_ts(prop["additionalProperties"], schemas)
            ts_type = f"Record<string, {val_type}>"
        elif "properties" in prop:
            ts_type = "object"  # Inline object — simplified
        else:
            ts_type = "Record<string, unknown>"

    if nullable:
        ts_type = f"{ts_type} | null"

    return ts_type


def schema_to_interface(name: str, schema: dict, all_schemas: dict) -> str:
    """Convert an OpenAPI schema to a TypeScript interface."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    if not props:
        return ""

    lines = [f"export interface {name} {{"]

    for prop_name, prop_def in sorted(props.items()):
        ts_type = openapi_type_to_ts(prop_def, all_schemas)
        optional = "?" if prop_name not in required else ""
        lines.append(f"  {prop_name}{optional}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)


def generate_typescript(schemas: dict[str, dict]) -> str:
    """Generate complete TypeScript file from all schemas."""
    header = [
        "// Auto-generated from OpenAPI schema definitions in docs.py",
        f"// Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "// Do not edit manually — regenerate with: python3 .ci/tools/generate-types.py",
        "",
    ]

    interfaces = []
    for name in sorted(schemas.keys()):
        schema = schemas[name]
        iface = schema_to_interface(name, schema, schemas)
        if iface:
            interfaces.append(iface)

    return "\n".join(header) + "\n".join(f"\n{iface}\n" for iface in interfaces)


def main():
    parser = argparse.ArgumentParser(description="Generate TypeScript from OpenAPI")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument("--docs-file", default=str(DOCS_FILE), help="Path to docs.py")
    args = parser.parse_args()

    docs_path = Path(args.docs_file)
    if not docs_path.exists():
        print(f"ERROR: {docs_path} not found", file=sys.stderr)
        sys.exit(1)

    schemas = extract_schemas_from_source(docs_path)
    if not schemas:
        print("WARNING: No schemas extracted from docs.py", file=sys.stderr)
        sys.exit(0)

    typescript = generate_typescript(schemas)

    if args.output:
        Path(args.output).write_text(typescript)
        print(f"Generated {len(schemas)} interfaces -> {args.output}", file=sys.stderr)
    else:
        print(typescript)

    sys.exit(0)


if __name__ == "__main__":
    main()
