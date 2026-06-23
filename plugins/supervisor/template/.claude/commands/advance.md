---
description: Mark one work package complete and let the FSM recompute building vs done. FSM transition.
argument-hint: '{"package":"<package-id>","completed_by":"<name>","evidence":"<commit/run/gate-ref>"}'
allowed-tools: Bash(bash ./.claude/commands/advance.sh:*)
---

You are performing the `advance` FSM transition: recording that one work package is complete. The single argument is a JSON object matching the `advance` schema. The command removes the package's `init/product/open/<package>` marker (the git delete that decrements work-remaining), advances the state, and prints the commit trailer. When the marker just removed was the last one, the FSM moves to `done`; otherwise it stays in `building` — the destination is computed from `git ls-files init/product/open/`, not asserted. Only mark a package complete when its evidence is real (a green gate, a merged commit), never optimistically.

!`bash ./.claude/commands/advance.sh '$ARGUMENTS'`
