# docs/ — two classes, and a file declares which one it is

**A file here is either CANONICAL or a PROPOSAL, and its status banner says
which.** Read a proposal as a design that was worked out and then parked, never
as a record of what the repository builds today.

This directory was PROPOSALS ONLY until 2026-08-26, and that line no longer
holds: `ctl-standard.md` landed as the written home of a rule that is in force.
The one-class sentence had to go with it — a canonical document filed under a
banner that calls the whole directory "proposals, not specifications" is a
document nobody is obliged to obey.

This README exists because the directory was invisible and unlabelled. Nothing
in the tree referenced `docs/`, it appeared in neither structure block, and its
one file carried the status line "build-ready notes" with no date. A cold reader
could not tell a proposal from a current spec — and the file names `_delta/mobile.sh`,
`mobile/Dockerfile` and `ARG PARENT_IMAGE`, none of which exist. A document that
names files nobody can find teaches the reader to distrust the whole set.

## What still records what the repository BUILDS

`.claude/rules/00-identity.md` and the Dockerfiles themselves. That has not
changed and a canonical file here does not compete with it: the identity file
is the record of the image SET — the manifest, the pins, the platform policy,
the publish order. A canonical `docs/` file states a rule that reaches BEYOND
this repository, which is why it could not live in the identity file: the
identity file describes what `.devcontainer` is, and the `ctl.sh` standard
governs eden, libs and infrastructure too.

When the two disagree, the identity file wins about this repository and the
canonical file wins about its own rule. Never restate one inside the other.

## The rule for a CANONICAL file

1. **The banner says `Class: CANONICAL`,** the date it was last judged true, and
   the program that owns it.
2. **It is the ONE home of its rule.** Nothing else in this repository restates
   it; other files CITE it. Two homes for one rule is the defect it exists to
   fix.
3. **Every claim carries its evidence** — the file and symbol a rule lives in, a
   measurement with its date, or a run id. Cite a SYMBOL rather than a line
   number wherever one exists: a line number goes stale on the next edit.
4. **A correction is written down, not silently applied.** When measurement
   refutes a claim the document made, the refutation stays in the file with the
   measurement that produced it.

## The rule for a PROPOSAL

1. **Carry a dated status banner at the top.** State what the file is, the date
   it was last judged true, and the program that owns it.
2. **Mark a name that the file PROPOSES.** A reader must be able to tell
   `_delta/mobile.sh` (proposed) from `_delta/components/agents.sh` (exists).
3. **Mark a superseded section where it stands.** Do not delete it. The
   reasoning stays useful, and a silent deletion loses why the option was
   rejected.
4. **Cite the file from the structure blocks.** A design nobody can find is a
   design nobody reviews.

## Current contents

| File | Class | State |
|---|---|---|
| `ctl-standard.md` | **canonical** | The `ctl.sh` standard: C1–C10 (safety) + I1–I7 (structure) + V1–V5 (the common verb vocabulary). Its CODE half is `_ctl/standard.sh`, held by `_ctl/tests/standard.test.sh`. Blueprint P0-6. What is NOT done and says so in the file: eden, libs and infrastructure sourcing it, and the `verbs --check` enforcer of the class table. |
| `image-notes-mobile.md` | proposal, part landed | The `mobile` category image. Its M1 NAMING step landed 2026-08-18 — the image is `mobile` and `mobile/` is its directory — so the file carries a DONE/PROPOSED marker per bullet. The re-parent onto `cloud`, `_delta/mobile.sh` and `matrix` are still proposals. Its `mobile-runner` child design is SUPERSEDED by the category-image program. |
