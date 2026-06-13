# poc/ — proofs of concept

Historical, pre-architecture experiments. **Status: donor material** (ADR-0009 ruling D): anything
here may be referenced or salvaged, but code enters `main` only through the same gates as new
work. Artifacts are deliberately *not* renamed to Eden (ADR-0002: historical artifacts keep their
names) and are not modified in place — their results are cited as evidence by the architecture
set.

| PoC | What it is | What it proved / feeds |
|---|---|---|
| `agents/` | Go agent daemon (`agentd`) + cpuload demo: dial-out management link, RPC bridge, tool dispatch, token tracking, embedded UI | The `management` (dial-out-only) pattern and agent transport/factory design (docs/research/02); donor for `apps/agent` and the F4 connector layer |
| `knowledge/` | Knowledge-library eval harness: 10 oracle-backed rules, 6 temptation tasks, 4 arms, 72-run matrix on omp + DeepSeek V4 Flash | The knowledge≠enforcement thesis (P7) and the post-cutoff-seam result cited by 08 §4; its rule schema and `_verify/` clean-room layout feed the kernel's test harness design (docs/research/03) |
| `codingharness/` | WS2 spike (09 §7): Go program driving one headless Claude Code session end-to-end, capturing the transcript and token ledger | De-risks the kernel's F4 adapter (ADR-0008) before `libs/go/codingharness` is contract-drafted |
| `agentsession-spike/` | REQ-0021 spike (C22): containerized headless Claude Code (node:22-slim, non-root, no ports, dial-out-only) authenticated by a `setup-token` OAuth token injected at runtime | Proves a normal membership user (`setup-token` → `CLAUDE_CODE_OAUTH_TOKEN`) can drive a sandboxed F4 session with no credential in any image layer/transcript; documents the auth flow and the bad-token silent-failure trap |

Results under `knowledge/results/` are provenance-stamped evidence — keep intact. Compiled
binaries (`knowledge/bin/`) are regenerable and gitignored.
