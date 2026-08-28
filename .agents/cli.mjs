#!/usr/bin/env node

import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const json = (path) => JSON.parse(readFileSync(resolve(root, path), "utf8"));
const config = json(".agents/config.json");
const ownership = json(".agents/ownership.json");
const policy = json(".agents/policy.json");
const namePattern = new RegExp(policy.namePattern);

function parseCanonical(path) {
  const content = readFileSync(resolve(root, path), "utf8");
  const name = content.match(/^name:\s*(.+)$/m)?.[1];
  const description = content.match(/^description:\s*(.+)$/m)?.[1];
  const body = content.replace(/^---\n[\s\S]*?\n---\n+/, "").trim();
  if (!name || !description || !body) throw new Error(`invalid canonical instruction: ${path}`);
  return { name, description, body };
}

function skillAdapter(name) {
  const { description } = parseCanonical(`.agents/skills/${name}/SKILL.md`);
  return `---\nname: ${name}\ndescription: ${description}\n---\n\n# Harness adapter\n\nRead \`.agents/skills/${name}/SKILL.md\` completely and follow it. This file only enables harness discovery.\n`;
}

function commandAdapter(name) {
  const path = `.agents/commands/${name}.md`;
  const content = readFileSync(resolve(root, path), "utf8");
  if (!content.match(/^description:\s*.+$/m)) throw new Error(`${path}: description is required`);
  return content;
}

function agentAdapter(name, harness) {
  const { description, body } = parseCanonical(`.agents/agents/${name}.md`);
  if (harness === "codex") {
    return `name = ${JSON.stringify(name)}\ndescription = ${JSON.stringify(description)}\ndeveloper_instructions = ${JSON.stringify(body)}\n`;
  }
  return `---\nname: ${name}\ndescription: ${description}\n---\n\n${body}\n`;
}

function generatedFiles() {
  const files = new Map();
  const skills = readdirSync(resolve(root, ".agents/skills"), { withFileTypes: true })
    .filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  for (const name of skills) {
    files.set(`.claude/skills/${name}/SKILL.md`, skillAdapter(name));
    files.set(`.omp/skills/${name}/SKILL.md`, skillAdapter(name));
  }
  const commands = readdirSync(resolve(root, ".agents/commands"))
    .filter((name) => name.endsWith(".md")).map((name) => name.slice(0, -3));
  for (const name of commands) {
    files.set(`.claude/commands/${name}.md`, commandAdapter(name));
    files.set(`.omp/commands/${name}.md`, commandAdapter(name));
  }
  for (const { agent } of ownership.projects) {
    files.set(`.codex/agents/${agent}.toml`, agentAdapter(agent, "codex"));
    files.set(`.claude/agents/${agent}.md`, agentAdapter(agent, "claude"));
    files.set(`.omp/agents/${agent}.md`, agentAdapter(agent, "omp"));
  }
  return files;
}

function sync(checkOnly) {
  const expected = generatedFiles();
  const managedRoots = [".claude/skills", ".omp/skills", ".claude/agents", ".omp/agents", ".codex/agents", ".claude/commands", ".omp/commands"];
  const actual = [];
  const walk = (directory) => {
    if (!existsSync(resolve(root, directory))) return;
    for (const entry of readdirSync(resolve(root, directory), { withFileTypes: true })) {
      const path = `${directory}/${entry.name}`;
      if (entry.isDirectory()) walk(path); else actual.push(path);
    }
  };
  managedRoots.forEach(walk);
  const drift = [];
  for (const relative of actual) {
    if (!expected.has(relative)) {
      if (checkOnly) drift.push(relative);
      else rmSync(resolve(root, relative));
    }
  }
  for (const [relative, content] of expected) {
    const path = resolve(root, relative);
    if (checkOnly) {
      if (!existsSync(path) || readFileSync(path, "utf8") !== content) drift.push(relative);
    } else {
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, content);
    }
  }
  if (drift.length) throw new Error(`stale generated adapters: ${drift.join(", ")}`);
}

function checkText(path, instruction) {
  const { name, description, body } = instruction;
  if (!namePattern.test(name)) throw new Error(`${path}: name must be lower-kebab-case`);
  if (description.length > policy.maxDescriptionCharacters) throw new Error(`${path}: description is too long`);
  if (body.length > policy.maxInstructionCharacters) throw new Error(`${path}: instructions are too long`);
  const text = `${description}\n${body}`.toLowerCase();
  const filler = policy.filler.find((phrase) => text.includes(phrase));
  if (filler) throw new Error(`${path}: remove filler phrase ${JSON.stringify(filler)}`);
}

function collectGarbage() {
  for (const directory of [".agents/agents", ".agents/skills"]) {
    const entries = readdirSync(resolve(root, directory), { withFileTypes: true });
    for (const entry of entries) {
      const relative = entry.isDirectory()
        ? `${directory}/${entry.name}/SKILL.md`
        : `${directory}/${entry.name}`;
      if (!namePattern.test(entry.name.replace(/\.md$/, ""))) throw new Error(`${relative}: path must be lower-kebab-case`);
      checkText(relative, parseCanonical(relative));
    }
  }
  for (const entry of readdirSync(resolve(root, ".agents/commands"))) {
    if (!entry.endsWith(".md") || !namePattern.test(entry.slice(0, -3))) throw new Error(`.agents/commands/${entry}: path must be lower-kebab-case`);
    const content = readFileSync(resolve(root, `.agents/commands/${entry}`), "utf8").toLowerCase();
    const filler = policy.filler.find((phrase) => content.includes(phrase));
    if (filler) throw new Error(`.agents/commands/${entry}: remove filler phrase ${JSON.stringify(filler)}`);
  }
}

function checkOwnership() {
  if (ownership.schemaVersion !== "eden.ownership/v1") throw new Error("unsupported ownership schema");
  const projects = new Set();
  const agents = new Set();
  for (const owner of ownership.projects) {
    if (!namePattern.test(owner.project) || !namePattern.test(owner.agent)) throw new Error("ownership names must be lower-kebab-case");
    if (projects.has(owner.project) || agents.has(owner.agent)) throw new Error(`duplicate ownership: ${owner.project}/${owner.agent}`);
    projects.add(owner.project); agents.add(owner.agent);
    const projectFile = owner.path === "." ? "project.json" : `${owner.path}/project.json`;
    if (!existsSync(resolve(root, projectFile))) throw new Error(`missing Nx project: ${owner.path}`);
    const project = json(projectFile);
    if (project.name !== owner.project) throw new Error(`Nx ownership mismatch: ${owner.project}`);
    if (!project.targets?.check) throw new Error(`${owner.project}: check target is required`);
    if (!existsSync(resolve(root, `.agents/agents/${owner.agent}.md`))) throw new Error(`missing agent: ${owner.agent}`);
  }
  const discovered = [];
  const skip = new Set([".git", ".nx", ".yarn", "node_modules", ".claude", ".codex", ".omp"]);
  const walk = (directory) => {
    for (const entry of readdirSync(resolve(root, directory), { withFileTypes: true })) {
      if (skip.has(entry.name)) continue;
      const path = directory ? `${directory}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(path);
      else if (entry.name === "project.json") discovered.push(directory || ".");
    }
  };
  walk("");
  const declared = ownership.projects.map(({ path }) => path).sort();
  if (discovered.sort().join(",") !== declared.join(",")) {
    throw new Error(`every Nx project needs one owner; found ${discovered.join(",")}; declared ${declared.join(",")}`);
  }
}

function check() {
  if (config.schemaVersion !== "eden.agents/v1") throw new Error("unsupported agent schema");
  const ids = config.harnesses.map(({ id }) => id).sort().join(",");
  if (ids !== "claude,codex,omp") throw new Error(`invalid harness set: ${ids}`);
  checkOwnership();
  for (const harness of config.harnesses) {
    for (const path of [harness.entrypoint, harness.skills, harness.agents, harness.commands].filter(Boolean)) {
      if (!existsSync(resolve(root, path))) throw new Error(`${harness.id} path is missing: ${path}`);
    }
  }
  collectGarbage();
  sync(true);
  console.log("agent contract: PASS");
}

function status() {
  for (const harness of config.harnesses) {
    const result = spawnSync(harness.command, ["--version"], { encoding: "utf8" });
    console.log(`${harness.id}\t${result.status === 0 ? (result.stdout || result.stderr).trim() : "missing"}`);
  }
}

function review() {
  check();
  const diff = spawnSync("git", ["diff", "--cached", "--", ".agents", ".codex", ".claude", ".omp", "*.md"], { encoding: "utf8" });
  if (diff.status !== 0) process.exit(diff.status ?? 1);
  if (!diff.stdout.trim()) return console.log("agent review: no staged instrumentation or prose");
  const prompt = `The deterministic agent contract passed. Review this staged diff for AI slop. Reject duplicated instructions, restated code, vague filler, needless scaffolding, misleading comments, or work that adds activity without capability. Small routing files and native harness adapters are required behavior, not duplication. Return only PASS or FAIL followed by concise findings.\n\n${diff.stdout}`;
  const result = spawnSync("codex", ["exec", "--color", "never", "-"], { input: prompt, encoding: "utf8", timeout: 120000 });
  if (result.error || result.status !== 0) throw new Error("agent review could not complete");
  process.stdout.write(result.stdout);
  if (!result.stdout.trimStart().startsWith("PASS")) process.exit(1);
}

const action = process.argv[2];
try {
  if (action === "sync") sync(false);
  else if (action === "check") check();
  else if (action === "status") status();
  else if (action === "review") review();
  else throw new Error("usage: cli.mjs <check|sync|status|review>");
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
