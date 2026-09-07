#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const config = JSON.parse(readFileSync(resolve(root, "secrets.json"), "utf8"));
const provider = process.env.EDEN_SECRETS_PROVIDER || config.provider;
const server = process.env.EDEN_SECRETS_SERVER || "";

function bw(args) {
  const result = spawnSync("bw", args, { encoding: "utf8" });
  if (result.error?.code === "ENOENT") throw new Error("bw CLI is not installed");
  if (result.status !== 0) throw new Error((result.stderr || result.stdout).trim());
  return result.stdout.trim();
}

function requireConfiguration() {
  if (provider !== "vaultwarden") throw new Error(`unsupported secrets provider: ${provider}`);
  if (!server.startsWith("https://")) throw new Error("EDEN_SECRETS_SERVER must use https://");
}

function status() {
  return JSON.parse(bw(["status"]));
}

function configure() {
  if (!server) {
    console.log("secrets server: not configured");
    return;
  }
  requireConfiguration();
  const current = status();
  if (current.serverUrl !== server) bw(["config", "server", server]);
  console.log(`secrets server: ${server}`);
}

function showStatus() {
  if (!server) {
    console.log(JSON.stringify({ provider, server: null, status: "not configured" }, null, 2));
    return;
  }
  requireConfiguration();
  const current = status();
  console.log(JSON.stringify({ provider, server: current.serverUrl, status: current.status }, null, 2));
}

try {
  const action = process.argv[2];
  if (action === "configure") configure();
  else if (action === "status") showStatus();
  else throw new Error("usage: ./ctl.sh <configure|status>");
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
