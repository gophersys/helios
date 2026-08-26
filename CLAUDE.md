# research-embedded

Type: research (gophersys taxonomy). The output is knowledge.

- The SFD process and its contracts live in `docs/sfd/` — read
  `docs/sfd/README.md` first. The graph and registry YAMLs are the
  machine-readable authorities; the .md files are their contracts.
- `gate.sh` is the entire safety net (no CI): devcontainer-only,
  FAIL-NOT-SKIP. Run it before any push.
- Any step that must be repeatable follows
  `.claude/rules/determinism-loop.md` — freeze, N blind instances,
  measure, ratchet. Determinism is earned, never asserted.
- Zephyr is the source of truth for hardware definitions; part numbers
  bind last (P4). The catalog (`catalog/`) is extracted, never written.
