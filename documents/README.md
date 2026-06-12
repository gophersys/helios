# documents/ — project eden's own document set

Eden is **project #1** of its own document system (doc 11, invariant E5). The documents here are
schema-validated against `schemas/document/v1` and enforced by `tools/documentvalidator`; render
them with `node docs/tools/render-documents.mjs documents/`.

`intake/` holds the raw founder-intake source material — the conversations the product tier's
`meta.source` entries point at. Source files are verbatim records: never edited, only appended.
