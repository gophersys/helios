# supervisor — the deterministic project-manager operating manual

This plugin is the **determinism heart** of the Eden supervisor agent: it turns an LLM
project-manager into a *repeatable* process via four mechanisms that only work together —

1. **A finite state machine** (`template/.claude/state/fsm.json`) — the project is always in one
   `current_state`; only a fixed legal transition set leaves it.
2. **Hard interfaces** — the agent acts ONLY through one typed slash-command per transition; every
   other tool is denied by `settings.json`.
3. **Git as the only memory** — every fact is a tracked file; guards are git predicates
   (`git ls-files init/decisions/open/`), unforgeable by prose; resume = checkout + re-read state.
4. **Gating hooks** — four lifecycle events enforce the cage and verify every commit's `fsm:`
   trailer.

It clones the SHAPE of `project-go` (manifest + `hooks/hooks.json` + lifecycle hook scripts +
session-start injection + a skill), but where project-go *advises* Go authoring, supervisor
*constrains* a project-manager into an FSM.

## The lifecycle

```
init ──▶ charter_drafted ──▶ charter_ratified ──▶ product_decomposed
     ──▶ decisions_open ──▶ decisions_ruled ──▶ planned ──▶ building ──▶ done
```

| Transition | Command | Writes | Guard (git predicate) |
|---|---|---|---|
| propose-charter | `/propose-charter` | `init/charter/charter.md` | charter not yet ratified |
| ratify-charter | `/ratify-charter` | `init/charter/.ratified` | a drafted charter exists |
| propose-questionnaire | `/propose-questionnaire` | `init/product/<id>.md` | charter ratified |
| open-decision | `/open-decision` | `init/decisions/open/<id>.md` | product decomposed |
| rule-decision | `/rule-decision` | `init/decisions/ruled/<id>.md` (moves from open) | a fork is open |
| plan | `/plan` | `init/plan/plan.md` + `init/product/open/<pkg>` markers | **no open fork** |
| advance | `/advance` | removes one `init/product/open/<pkg>` marker | a plan exists |

`/state-show` is the read-only "you are here" — current state + the one legal transition + each
guard's status.

## Layout

```
plugins/supervisor/
├── .claude-plugin/plugin.json        # plugin manifest (validated by `claude plugin validate`)
├── hooks/
│   ├── hooks.json                    # wires the 4 lifecycle events (plugin install path)
│   ├── _shim.sh                      # resolver: delegate to the project's rendered template hooks
│   └── {session-start,gate-tool,gate-commit,stop-gate}.sh   # thin shims (ONE logic home: template)
├── skills/supervisor-operating-manual/SKILL.md
├── AGENT-TEMPLATE.md                 # the supervisor AgentTemplate (orchestrator TemplateStore data)
└── template/.claude/                 # THE rendered operating manual an agent runs as
    ├── settings.json                 # THE LAW: deny-by-default + the 4 lifecycle hooks
    ├── state/fsm.json                # the FSM (current_state + transition table + git guards)
    ├── instructions/00..40.md        # identity / state-machine / git-protocol / hard-interfaces / schemas
    ├── commands/                     # the 8 typed slash-commands (.md + .sh) + _supervisor.sh
    ├── hooks/                        # session-start / gate-tool / gate-commit / stop-gate (+ _hooklib.sh)
    └── schemas/                      # the JSON Schemas every command payload validates against
```

## Two run modes

- **Direct (the supervisor agent).** An agent given `template/.claude/` as its project config runs
  the FSM directly: its `settings.json` wires the four hooks and denies everything outside the hard
  interface. This is what an orchestrator-spawned supervisor pod dogfoods.
- **Installed plugin.** `claude plugin marketplace add ./libs && claude plugin install
  supervisor@eden-libs` wires the same four events from the plugin root; the plugin shims delegate
  to the project's rendered `template/.claude/hooks/*` so the determinism logic has one home and
  is a no-op in any non-supervisor project that merely has it installed.

## Runtime state (generated, not tracked by the plugin)

A live supervisor run produces `init/`, `state/fsm.json` mutations, and `audit/log.ndjson` **in the
project repo** — that is the supervised project's git, not this plugin's. The `template/.claude/`
ships the *initial* `state/fsm.json` (`current_state: init`); rendering the template into a fresh
project seeds the starting state.

## Validate

```bash
claude plugin validate libs/plugins/supervisor
claude plugin validate libs
# shellcheck the hooks + commands in the devcontainer:
docker exec -u dev base-devcontainer bash -lc 'cd /workspace && shellcheck libs/plugins/supervisor/template/.claude/hooks/*.sh libs/plugins/supervisor/template/.claude/commands/*.sh libs/plugins/supervisor/hooks/*.sh'
```

## Relationship to the orchestrator

The supervisor is **data** the orchestrator resolves: `AGENT-TEMPLATE.md` documents the
`orchestrator.AgentTemplate` (Routing `Role:supervisor → {claude-code, opus-4.8}`, broad-but-clamped
Grants, a long Budget, the strict SandboxSpec) that a `TemplateStore.Resolve` returns. The
orchestrator folds it into an `agentsession.Spec` + a `workspaceprovider.WorkspaceSpec` and tracks
the session; the operating manual here is what runs *inside* that session.
