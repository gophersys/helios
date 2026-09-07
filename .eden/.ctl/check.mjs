#!/usr/bin/env node

import { readFileSync } from "node:fs";

const read = (path) => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const model = read("model.json");
const names = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

if (model.schemaVersion !== "eden.system/v1") throw new Error("unsupported system model");
if (model.kernel.join(",") !== "intent,plan,work,evidence,decision") throw new Error("invalid lifecycle kernel");

for (const [name, file] of Object.entries(model.tracks)) {
  const practice = read(file);
  if (practice.schemaVersion !== "eden.practice/v1" || practice.name !== name) throw new Error(`${file}: invalid identity`);
  if (!practice.purpose || !practice.standardBasis?.length || !practice.states?.length || !practice.transitions?.length) throw new Error(`${file}: incomplete practice`);
  const states = new Set();
  for (const state of practice.states) {
    if (!names.test(state.name) || states.has(state.name)) throw new Error(`${file}: invalid state ${state.name}`);
    if (!state.outcome || !state.evidence?.length) throw new Error(`${file}: incomplete state ${state.name}`);
    states.add(state.name);
  }
  for (const transition of practice.transitions) {
    if (!states.has(transition.from) || !states.has(transition.to) || !transition.decision) throw new Error(`${file}: invalid transition`);
  }
}

console.log("system contract: PASS (research, software)");
