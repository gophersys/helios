# eden

Eden is a platform for building and operating software with AI agents. You describe what you
want; Eden turns it into documents, the documents into a working system, and keeps that system
deployed, observed, and maintained — while you make decisions instead of supervising agents.

This repo is Eden being built — by the same process Eden will offer its users.

## Overwhelmed? Read only this section

The whole system is one loop:

1. **You talk** → an agent writes it down as structured documents (requirements, workflows).
2. **You approve** the documents (or mark them up — they version like code).
3. **Agents build** against frozen contracts, in isolated workspaces, in parallel.
4. **Machines verify** in clean rooms — agents never grade their own work.
5. **You rule at gates** — short, queued decisions. Never live supervision.
6. Repeat. Every artifact traces back to something you said.

Everything in `docs/` exists to make that loop trustworthy. You do not need to read most of it.

**Your three documents** (≈30 min total): [`docs/architecture/00-charter.md`](docs/architecture/00-charter.md)
(what and why) · [`docs/architecture/06-dogfooding-bootstrap.md`](docs/architecture/06-dogfooding-bootstrap.md)
(how it gets built) · [`docs/architecture/09-build-execution-plan.md`](docs/architecture/09-build-execution-plan.md)
(what's next, §8 = the build list).

**Your browser front door:** generate and open `docs/eden-atlas.html`
(`node docs/tools/render-atlas.mjs`) — diagrams, reading paths, every open question in one place.

**Everything else is reference.** It exists so agents and future sessions stay consistent — it is
written *to be consulted, not read*. Treat it like a law library, not a novel.

## The five kinds of documents (and that's all there are)

| Kind | Where | In one line |
|---|---|---|
| Canonical specs | `docs/architecture/` | The decided truth. Numbered 00–12 + decision records (ADRs). Conflicts resolve here. |
| Research notes | `docs/research/` | Dated findings with sources. Promoted into specs, never edited. |
| Upstream corpus | `docs/upstream/` | The pre-Eden research this all grew from. Imported verbatim, consulted rarely. |
| Project documents | `documents/` | Eden's own product docs — what *you* asked for, schema-checked, versioned through gates. |
| Attic | `docs/attic/` | Superseded material, preserved verbatim. Never authority. |

Directory `README.md`s orient; they never decide. The full rules: [`docs/README.md`](docs/README.md).

## Layout

```
eden/
├── documents/         # Eden's own product docs + your intake transcripts
├── docs/              # architecture (canon) · research · upstream · attic · tools
├── schemas/           # the hard schemas every project document validates against
├── tools/             # documentvalidator — the enforcement tooling
├── apps/              # (to be built) backend · frontend · desktop · agent
├── poc/               # proofs of concept — salvage material, gated
└── libs/ infrastructure/ .devcontainer/   # submodules
```

## Repo mechanics

Clone with `git submodule update --init --recursive`. CI: `bash .ci/ctl.sh affected-check`
(no-ops until `yarn install`). Conventions, naming law, and agent rules live in
[`CLAUDE.md`](CLAUDE.md); the canonical naming standard is `docs/architecture/10-library-system.md` §5.
