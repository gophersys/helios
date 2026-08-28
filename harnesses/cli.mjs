#!/usr/bin/env node

import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const capabilities = JSON.parse(readFileSync(resolve(root, "harnesses/capabilities.json"), "utf8"));
const versions = Object.fromEntries(
  readFileSync(resolve(root, "harnesses/versions.env"), "utf8")
    .split("\n")
    .filter((line) => /^[A-Z][A-Z0-9_]*=/.test(line))
    .map((line) => line.split("=", 2)),
);

const adapter = (name) => `---
name: ${name}
description: Develop, test, review, and deliver changes in Eden through its cloud devcontainer and Nx project targets.
---

# Harness adapter

The canonical Eden skill is [\`.agents/skills/${name}/SKILL.md\`](../../../.agents/skills/${name}/SKILL.md).
Read it completely and follow it. This file exists only for harness discovery and
must not define a second workflow.
`;

const generated = new Map([
  [".claude/skills/dev/SKILL.md", adapter("dev")],
  [".omp/skills/dev/SKILL.md", adapter("dev")],
]);

function sync(checkOnly) {
  const drift = [];
  for (const [relative, expected] of generated) {
    const path = resolve(root, relative);
    if (checkOnly) {
      if (!existsSync(path) || readFileSync(path, "utf8") !== expected) drift.push(relative);
      continue;
    }
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, expected);
  }
  if (drift.length) throw new Error(`generated harness adapters are stale: ${drift.join(", ")}`);
}

function check() {
  if (capabilities.schemaVersion !== "eden.harnesses/v1") throw new Error("unsupported capabilities schema");
  if (capabilities.canonicalSkills !== ".agents/skills") throw new Error("canonical skill root must be .agents/skills");
  const ids = capabilities.harnesses.map(({ id }) => id).sort().join(",");
  if (ids !== "claude,codex,omp") throw new Error(`expected claude,codex,omp; found ${ids}`);
  for (const harness of capabilities.harnesses) {
    if (!existsSync(resolve(root, harness.entrypoint))) throw new Error(`${harness.id} entrypoint is missing`);
    if (!existsSync(resolve(root, harness.skills))) throw new Error(`${harness.id} skill root is missing`);
  }
  for (const key of ["CLAUDE_CODE_VERSION", "CODEX_VERSION", "OMP_VERSION"]) {
    if (!versions[key]) throw new Error(`missing version pin: ${key}`);
  }
  sync(true);
  console.log("harness contract: PASS");
}

function status() {
  for (const harness of capabilities.harnesses) {
    const result = spawnSync(harness.command, ["--version"], { encoding: "utf8" });
    const version = result.status === 0 ? (result.stdout || result.stderr).trim() : "missing";
    console.log(`${harness.id}\t${version}\t${harness.skills}`);
  }
}

const action = process.argv[2];
try {
  if (action === "sync") sync(false);
  else if (action === "check") check();
  else if (action === "status") status();
  else throw new Error("usage: cli.mjs <check|sync|status>");
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
