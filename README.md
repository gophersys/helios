# eden

Eden is a platform to build software with AI agents and to operate it. You describe what you
want. Eden turns your description into documents, then turns the documents into a working system.
Eden keeps that system deployed, observed and maintained. You make the decisions. You do not
supervise the agents.

This repository is the build of Eden. It uses the same process that Eden gives to its users.

## Read only this section first

The whole system is one loop:

1. **You speak.** An agent writes your words as structured documents: requirements and workflows.
2. **You approve the documents**, or you mark them up. The documents have versions, like code.
3. **The agents build.** They work against frozen contracts, in isolated workspaces, at the same
   time.
4. **The machines verify the work** in clean rooms. An agent never verifies its own work.
5. **You decide at the gates.** The decisions are short and they wait in a queue. You never
   supervise the work in real time.
6. Then the loop starts again. Every artifact traces back to something that you said.

Everything in `docs/` makes that loop trustworthy. You do not need to read most of it.

**Your 3 documents** (about 30 minutes in total):

- [`docs/architecture/00-charter.md`](docs/architecture/00-charter.md) — what Eden is and why.
- [`docs/architecture/06-dogfooding-bootstrap.md`](docs/architecture/06-dogfooding-bootstrap.md) —
  how Eden gets built.
- [`docs/architecture/09-build-execution-plan.md`](docs/architecture/09-build-execution-plan.md) —
  what comes next. §8 is the build list.

**The browser view:** generate `docs/eden-atlas.html` with `node docs/tools/render-atlas.mjs`,
then open it. It holds the diagrams, the reading paths and every open question in one place.

**Everything else is reference material.** It keeps the agents and the later sessions consistent.
Read only the part that you need at the time. Do not read it from start to end.

## The 5 kinds of documents

There are no other kinds.

| Kind | Where | In one line |
|---|---|---|
| Canonical specs | `docs/architecture/` | The decisions that are made. The files are numbered 00–12, with the decision records (ADRs). A conflict is resolved here. |
| Research notes | `docs/research/` | Findings with a date and the sources. They move into the specs. Nobody edits them. |
| Upstream corpus | `docs/upstream/` | The research from before Eden. Imported without a change. Consulted rarely. |
| Project documents | `documents/` | The product documents of Eden. They hold what *you* asked for. A schema checks them. They get a version at each gate. |
| Attic | `docs/attic/` | Superseded material, kept without a change. Never an authority. |

A directory `README.md` gives orientation. It never makes a decision. The full rules are in
[`docs/README.md`](docs/README.md).

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

## Repository mechanics

Clone the repository with `git submodule update --init --recursive`. The CI command is
`bash .ci/ctl.sh affected-check`, and it does nothing until you run `yarn install`.
[`CLAUDE.md`](CLAUDE.md) holds the conventions, the naming law and the agent rules. The canonical
naming standard is `docs/architecture/10-library-system.md` §5.
