# 40 — Artifact schemas: the typed payloads

Every transition command takes a single JSON payload validated against a JSON Schema under
`.claude/schemas/`. The command refuses a payload that fails its schema, so a malformed artifact
never reaches git. The schemas are the authority; the shapes below are the quick reference.

## `charter` → `/propose-charter`

```json
{
  "title": "Eden bootstrap",
  "problem": "Plain-language statement of the problem being solved.",
  "outcomes": ["A measurable success condition", "Another"],
  "non_goals": ["Explicitly out of scope"],
  "constraints": ["Hard limit: budget / deadline / technology"],
  "stakeholders": ["Role or person who owns an outcome"]
}
```

## `ratification` → `/ratify-charter`

```json
{ "ratified_by": "Mateo Segura", "ratified_at": "2026-06-22T12:00:00Z" }
```

The command fingerprints the ratified charter into `init/charter/.ratified` so a later silent edit
of the charter is detectable.

## `work-item` → `/propose-questionnaire`

```json
{
  "id": "user-login",
  "title": "User can log in",
  "summary": "What this unit delivers and why it belongs to the charter.",
  "acceptance": ["Observable condition under which this is complete"],
  "depends_on": ["another-work-item-id"]
}
```

`id` is a lowercase-kebab full-word slug (HNS-1), and is the filename stem `init/product/<id>.md`.

## `decision` → `/open-decision`

```json
{
  "id": "storage-engine",
  "question": "Which storage engine backs the catalog?",
  "context": "Why this fork exists and what depends on it.",
  "options": [
    { "name": "postgres", "tradeoffs": "Relational, mature; heavier ops." },
    { "name": "sqlite", "tradeoffs": "Zero-ops, embedded; single-writer." }
  ],
  "affects": ["catalog"]
}
```

At least two mutually exclusive options, each with tradeoffs. An open decision blocks `/plan`.

## `ruling` → `/rule-decision`

```json
{
  "id": "storage-engine",
  "chosen": "postgres",
  "rationale": "Why this option was chosen over the others.",
  "ruled_by": "Mateo Segura"
}
```

`id` must match an open decision; `chosen` must be one of its option names (the command cross-checks
both). The command moves `open/<id>.md` → `ruled/<id>.md` — the git move that clears the fork.

## `plan` → `/plan`

```json
{
  "packages": [
    { "id": "foundation", "work_items": ["user-login"], "order": 0,
      "budget": { "max_cost_micros": 0, "max_turns": 0 } }
  ]
}
```

Every referenced `work_items` id must exist under `init/product/`. The command seeds one
`init/product/open/<package>` marker per package — the work-remaining tokens `/advance` consumes.

## `advance` → `/advance`

```json
{ "package": "foundation", "completed_by": "Mateo Segura", "evidence": "commit abc123 / gate green" }
```

`package` must match an open `init/product/open/<package>` marker. Only advance on REAL evidence
(a green gate, a merged commit) — never optimistically. When the last marker is removed, the FSM
moves to `done`.
