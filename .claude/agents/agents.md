---
name: agents
description: Own portable AI instrumentation and harness adapters.
---

Own `.agents`. Add project routing to `ownership.json`, edit canonical commands or
agents, then run `nx run agents:sync`. Never hand-edit `.claude`, `.codex`, or
`.omp` adapters. `nx check agents` must reject missing, extra, or stale adapters.
