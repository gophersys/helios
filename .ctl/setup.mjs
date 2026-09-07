#!/usr/bin/env node

import { spawnSync } from "node:child_process";

const result = spawnSync("git", ["config", "core.hooksPath", ".githooks"], {
  stdio: "inherit",
});
if (result.status !== 0) process.exit(result.status ?? 1);
console.log("workspace hooks: .githooks");
