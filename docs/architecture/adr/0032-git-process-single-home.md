# ADR-0032 — one git process, one home, no legacy

- **Status:** accepted
- **Date:** 2026-08-25
- **Deciders:** Mateo
- **Supersedes:** ADR-0019 (unified git workflow and merge agents), and with it
  `docs/architecture/13-versioning-and-git-workflow.md`

## Context

ADR-0019 decided a git workflow in 2026-06 and made doc 13 its canonical home.
`.claude/rules/git-process.md` was then authored as THE development process for
eden, and the two disagreed on the things a git process exists to settle:

| subject | ADR-0019 / doc 13 | git-process.md |
| --- | --- | --- |
| merge method | fast-forward-only | one merge commit, `--merge` |
| branch grammar | `<class>/<slug>[/run-<id>]`, classes `docs·arch·impl·infra·fix·release·ws<N>` | `<type>/<slug>`, types `feat·fix·chore·docs·ci·test·refactor` |
| commit trailers | `Spec:` `Requirement:` `Run:` | none |
| attribution | no AI/LLM attribution | agent authors as Claude (ADR-0010 carried the old rule too) |
| unattended merge | `auto` classes only | four merge conditions |

An adversarial refutation caught this before the rule landed. eden's own
`CLAUDE.md` says one concept has one home and a made decision is not reopened,
so two homes for the git process was itself the defect — independently of which
one was right.

## Decision

**`.claude/rules/git-process.md` is the SINGLE HOME of the git process.** Its
model governs: short-lived branch from fresh `origin/main`, its own worktree,
one PR, **one merge commit**, `<type>/<slug>` naming, the four merge conditions,
and §13 attribution.

**ADR-0019 and doc 13 are superseded and their content is deleted.** No
compatibility layer, no parallel grammar, no deprecation window.

### The human gate, EXERCISED

`git-process.md` §5 reserves a reopened ADR to Mateo, and §13 rule 4 counts a
gate as exercised only when the record quotes his verbatim words with a
timestamp. Both conditions are met here.

> **Mateo, 2026-08-25 ~15:36 MST, verbatim:**
> "super seed and delete everything related to the old provess no legacy no
> nothing"

Normalized reading: *supersede, and delete everything related to the old
process — no legacy, no nothing.*

This ADR is that supersession. No agent chose the merge method; the decision is
his, and the quote above is the evidence rather than an inference from it.

## Consequences

**Deleted, not deprecated:**

- `docs/architecture/13-versioning-and-git-workflow.md` — removed.
- ADR-0019 — reduced to a tombstone pointing here. Its content is gone.
- `hook_check_branch_name` in `.githooks/lib/common.sh`, its call in
  `.githooks/pre-push`, and `.githooks/lib/branchname_test.sh` — removed. The
  old grammar is no longer enforced anywhere.
- `.claude/agents/merge-agent.md` — rewritten to this process: merge commits,
  the four merge conditions, `<type>/<slug>`, §13 attribution. No
  fast-forward-only, no artifact trailers, no class grammar.
- ADR-0010 §6's "no AI/LLM attribution lines" — amended, because §13 reverses it.

**Deliberately UNTOUCHED — the library contract is a different subject.**
`docs/architecture/contracts/gitrepository.md` keeps every fast-forward-only
statement. That contract governs a Go LIBRARY's push and pull semantics, where
ff-only is a safety property that stops a silent three-way merge inside library
code with no human reading it. It is not a statement about how humans and agents
merge pull requests. Blueprint **P2-0** owns that contract; this ADR does not
open it. The two uses of one phrase are two subjects, and conflating them would
weaken a real safety guarantee to tidy a document.

**What propagates:** any future reference to a git workflow cites
`.claude/rules/git-process.md`. A CI agent sees only the checkout, so the rule
living in the repository is what makes it reachable at all.
