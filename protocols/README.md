# libs/protocols

Coming — will host language-agnostic schema and protocol definitions
(Protocol Buffers, JSON Schema, OpenAPI, Avro, CBOR, etc.) shared across
every brain-ecosystem project.

## Rationale

A protocol defined in `.proto` / `.yaml` / `.json` is the source of
truth. Language bindings are generated from it. Keeping the schema in
one place — versioned, reviewed, propagated — guarantees every consumer
(TypeScript backend, Python ML service, Rust edge daemon, Zephyr
firmware) agrees on the same wire format.

## Layout (once populated)

Each protocol family lives in its own directory directly under this
subtree:

```
protocols/
├── <protocol-name>/
│   ├── project.json           # Nx wiring, nx:run-commands only
│   ├── ctl.sh                 # bash source of truth, chmod +x
│   ├── schemas/               # .proto / .yaml / .json source files
│   └── generated/             # generated bindings, gitignored or per-lang subdirs
```

## Verbs

Every protocol's `ctl.sh` implements, at minimum:

- `lint`              — validate schema syntax (e.g. `buf lint` for protobuf)
- `generate-typescript` — regenerate TypeScript bindings
- `generate-python`     — regenerate Python bindings
- `generate-rust`       — regenerate Rust bindings
- `generate-zephyr`     — regenerate C headers suitable for Zephyr firmware

Subsets of these verbs apply depending on which languages actually
consume the protocol. Add only what is used.

Target cache policy:

- `lint`, `generate-*` → `cache: true` with `schemas/**` as `inputs`

## Consumers

Generated bindings are consumed by libraries in the sibling subtrees
(`libs/typescript/<lib>`, `libs/python/<lib>`, etc.) which wrap them
with ergonomic APIs before reaching application code.

## Authoring reference

See the skill documentation at:

```
brain/.claude/skills/development-nx-run-command/
```
