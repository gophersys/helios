#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../../..");
const run = (command, args) => {
  const result = spawnSync(command, args, { cwd: root, encoding: "utf8" });
  if (result.status !== 0) throw new Error((result.stderr || result.stdout).trim());
  return result.stdout.trim();
};

const branch = process.env.GITHUB_HEAD_REF || run("git", ["branch", "--show-current"]);
if (branch && branch !== "main" && !/^(feat|fix|chore|docs|ci|test)\/[a-z0-9]+(?:-[a-z0-9]+)*$/.test(branch)) {
  throw new Error(`invalid change branch: ${branch}`);
}

const baseRef = process.env.GITHUB_BASE_REF ? `origin/${process.env.GITHUB_BASE_REF}` : "origin/main";
let base;
try {
  base = run("git", ["merge-base", "HEAD", baseRef]);
} catch {
  base = run("git", ["merge-base", "HEAD", "main"]);
}

const changed = new Set(run("git", ["diff", "--name-only", base]).split("\n").filter(Boolean));
for (const path of run("git", ["ls-files", "--others", "--exclude-standard"]).split("\n").filter(Boolean)) changed.add(path);
if (!changed.size) {
  console.log("change contract: PASS (no changes)");
  process.exit(0);
}

const ownership = JSON.parse(readFileSync(resolve(root, ".agents/ownership.json"), "utf8")).projects;
const generated = new Map([[".claude", "agents"], [".codex", "agents"], [".omp", "agents"]]);
const owners = new Set();
for (const path of changed) {
  const generatedOwner = [...generated].find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`))?.[1];
  if (generatedOwner) {
    owners.add(generatedOwner);
    continue;
  }
  const matches = ownership
    .filter(({ path: ownerPath }) => ownerPath !== "." && (path === ownerPath || path.startsWith(`${ownerPath}/`)))
    .sort((a, b) => b.path.length - a.path.length);
  owners.add(matches[0]?.project || "workspace");
}

run("git", ["diff", "--check", base]);
const checks = [...owners].filter((project) => project !== "change").sort();
for (const project of checks) {
  const owner = ownership.find((entry) => entry.project === project);
  const file = owner.path === "." ? "project.json" : `${owner.path}/project.json`;
  const config = JSON.parse(readFileSync(resolve(root, file), "utf8"));
  if (!config.targets?.check) throw new Error(`${project}: changed project has no check target`);
}

console.log(`change contract: PASS (${changed.size} files)`);
console.log(`required checks: ${checks.length ? checks.join(", ") : "none"}`);
