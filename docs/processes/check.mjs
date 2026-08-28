#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const read = (path) => JSON.parse(readFileSync(resolve(import.meta.dirname, path), "utf8"));
const registry = read("registry.json");
const ownership = JSON.parse(readFileSync(resolve(root, ".agents/ownership.json"), "utf8"));
const agents = new Set(ownership.projects.map(({ agent }) => agent).concat("process-author", "project-owner"));
const names = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

for (const [command, entries] of [["request", registry.requests], ["question", registry.questions]]) {
  for (const [name, file] of Object.entries(entries)) {
    if (!names.test(name) || file !== `${name}.json`) throw new Error(`invalid process registration: ${name}`);
    const process = read(file);
    const allowed = ["schemaVersion", "name", "command", "coordinator", "input", "steps", "proof"];
    const extra = Object.keys(process).find((key) => !allowed.includes(key));
    if (extra) throw new Error(`${file}: unknown field ${extra}`);
    if (process.schemaVersion !== "eden.process/v1" || process.name !== name || process.command !== command) throw new Error(`${file}: invalid identity`);
    for (const field of ["coordinator", "input", "proof"]) if (!process[field]) throw new Error(`${file}: missing ${field}`);
    if (!agents.has(process.coordinator)) throw new Error(`${file}: unknown coordinator ${process.coordinator}`);
    if (!Array.isArray(process.steps) || process.steps.length === 0) throw new Error(`${file}: steps are required`);
    for (const step of process.steps) {
      const extraStep = Object.keys(step).find((key) => !["name", "agent", "action", "proof"].includes(key));
      if (extraStep) throw new Error(`${file}: unknown step field ${extraStep}`);
      if (!names.test(step.name) || !agents.has(step.agent)) throw new Error(`${file}: invalid step ${step.name}`);
      if (!step.action || !step.proof) throw new Error(`${file}: incomplete step ${step.name}`);
    }
    if (!existsSync(resolve(import.meta.dirname, `${name}.md`))) throw new Error(`${name}.md is missing`);
  }
}

console.log("process contract: PASS");
