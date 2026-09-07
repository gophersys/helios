#!/usr/bin/env node

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, relative, resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const markdown = ["README.md", "AGENTS.md", "CLAUDE.md"];
const walk = (directory) => {
  for (const entry of readdirSync(resolve(root, directory), { withFileTypes: true })) {
    const path = `${directory}/${entry.name}`;
    if (entry.isDirectory()) walk(path);
    else if (entry.name.endsWith(".md")) markdown.push(path);
  }
};
walk("docs");

const projects = new Map();
const projectWalk = (directory) => {
  for (const entry of readdirSync(resolve(root, directory), { withFileTypes: true })) {
    if ([".git", ".nx", ".yarn", "node_modules", ".claude", ".codex", ".omp"].includes(entry.name)) continue;
    const path = directory ? `${directory}/${entry.name}` : entry.name;
    if (entry.isDirectory()) projectWalk(path);
    else if (entry.name === "project.json") {
      const project = JSON.parse(readFileSync(resolve(root, path), "utf8"));
      projects.set(project.name, new Set(Object.keys(project.targets ?? {})));
    }
  }
};
projectWalk("");

const knownCommands = new Set(["bw", "cd", "codex", "devcontainer", "export", "git", "nx"]);
const checkNx = (line, source) => {
  const words = line.trim().split(/\s+/);
  if (words[1] === "run") {
    const [project, target] = (words[2] ?? "").split(":");
    if (!projects.get(project)?.has(target)) throw new Error(`${source}: unknown Nx target ${words[2]}`);
  } else if (words[1] === "run-many") {
    const target = words[words.indexOf("-t") + 1];
    if (!target) throw new Error(`${source}: nx run-many needs -t <target>`);
  } else {
    const target = words[1];
    const project = words[2];
    if (!projects.get(project)?.has(target)) throw new Error(`${source}: unknown Nx command ${target} ${project}`);
  }
};

for (const path of [...new Set(markdown)].sort()) {
  const content = readFileSync(resolve(root, path), "utf8");
  for (const match of content.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
    const link = match[1].split("#", 1)[0];
    if (!link || /^(https?:|mailto:)/.test(link)) continue;
    if (!existsSync(resolve(root, dirname(path), link))) throw new Error(`${path}: broken link ${link}`);
  }
  for (const match of content.matchAll(/```(?:bash|sh)\n([\s\S]*?)```/g)) {
    const script = match[1];
    const syntax = spawnSync("bash", ["-n"], { input: script, encoding: "utf8" });
    if (syntax.status !== 0) throw new Error(`${path}: invalid shell block: ${syntax.stderr.trim()}`);
    for (const line of script.split("\n").map((line) => line.trim()).filter(Boolean)) {
      const command = line.split(/\s+/, 1)[0];
      if (!knownCommands.has(command)) throw new Error(`${path}: undocumented command contract ${command}`);
      if (command === "nx") checkNx(line, path);
    }
  }
}

console.log(`docs contract: PASS (${markdown.length} files, ${projects.size} projects)`);
