#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(readFileSync(resolve(root, "config.json"), "utf8"));
const provider = process.env.EDEN_SECRETS_PROVIDER || config.provider;
const server = process.env.EDEN_SECRETS_SERVER || config.server;

function bw(args) {
  const result = spawnSync("bw", args, { encoding: "utf8" });
  if (result.error?.code === "ENOENT") throw new Error("bw CLI is not installed");
  if (result.status !== 0) throw new Error((result.stderr || result.stdout).trim());
  return result.stdout.trim();
}

function status() {
  return JSON.parse(bw(["status"]));
}

function requireProvider() {
  if (provider !== "vaultwarden") throw new Error(`unsupported secrets provider: ${provider}`);
  if (!server.startsWith("https://")) throw new Error("secrets server must use https://");
}

function configure() {
  requireProvider();
  const current = status();
  if (current.serverUrl !== server) bw(["config", "server", server]);
  console.log(`secrets server: ${server}`);
}

function check() {
  requireProvider();
  const current = status();
  if (current.serverUrl !== server) {
    throw new Error(`bw server is ${current.serverUrl || "unset"}; expected ${server}; run: nx run secrets:configure`);
  }
  console.log(`secrets contract: PASS (${current.status})`);
}

function showStatus() {
  requireProvider();
  const current = status();
  console.log(JSON.stringify({ provider, server: current.serverUrl, status: current.status }, null, 2));
}

try {
  const action = process.argv[2];
  if (action === "configure") configure();
  else if (action === "check") check();
  else if (action === "status") showStatus();
  else throw new Error("usage: cli.mjs <check|configure|status>");
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
