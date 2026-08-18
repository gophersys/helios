# docs/ — proposals, not specifications

**Everything in this directory describes an image that does not exist.** Read a
file here as a design that was worked out and then parked, never as a record of
what the repository builds today. The record of what it builds is
`.claude/rules/00-identity.md` and the Dockerfiles themselves.

This README exists because the directory was invisible and unlabelled. Nothing
in the tree referenced `docs/`, it appeared in neither structure block, and its
one file carried the status line "build-ready notes" with no date. A cold reader
could not tell a proposal from a current spec — and the file names `_delta/mobile.sh`,
`mobile/Dockerfile` and `ARG PARENT_IMAGE`, none of which exist. A document that
names files nobody can find teaches the reader to distrust the whole set.

## The rule for a file here

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
| `image-notes-mobile.md` | proposal, part landed | The `mobile` category image. Its M1 NAMING step landed 2026-08-18 — the image is `mobile` and `mobile/` is its directory — so the file carries a DONE/PROPOSED marker per bullet. The re-parent onto `cloud`, `_delta/mobile.sh` and `matrix` are still proposals. Its `mobile-runner` child design is SUPERSEDED by the category-image program. |
