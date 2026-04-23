---
name: core-spec:spec
description: "Create, view, or manage project specifications"
allowed-tools: Read, Write, Glob, Agent
---

# /spec Command

Route spec operations to appropriate workflow.

## Usage

| Command | Action |
|---------|--------|
| `/spec` | Show active spec or create new |
| `/spec new <name>` | Create new spec |
| `/spec status` | Show current status |
| `/spec resume` | Continue execution |
| `/spec list` | List all specs in session |

## Routing

1. Parse command arguments
2. Check for active spec in `.claude/specs/sessions/`
3. Route to spec-design or spec-execute skill
4. Update tracking after operation
