# schemas/ — machine-validated artifact schemas

Hard schemas enforcing invariant E2. Canonical specification:
`docs/architecture/11-project-document-system.md`; rulings: ADR-0011.

```
schemas/document/v1/        # project document schemas (JSON Schema 2020-12)
├── envelope.schema.json    # the common envelope every document carries (doc 11 §4)
├── <type>.schema.json      # one per document type (doc 11 §6), allOf-extends the envelope
└── examples/<project>/     # a worked example project — validator test fixtures
```

- `$id` is the logical URI `eden://document/v1/<name>` (doc 11 Q2); validators preload the
  directory to resolve cross-file references.
- Schemas are semver'd and version with the platform release; breaking changes ship with
  migrations (06 §3). Documents pin `schema_version`.
- Validation entrypoint: `tools/documentvalidator` (shape + traceability rules T1–T7).
