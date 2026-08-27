#!/usr/bin/env node

import { existsSync, readFileSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const contract = JSON.parse(
  readFileSync(resolve(repositoryRoot, 'docs/engineering/system.json'), 'utf8'),
);
const schema = JSON.parse(
  readFileSync(resolve(repositoryRoot, 'docs/engineering/system.schema.json'), 'utf8'),
);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function isAvailableRepositoryPath(path) {
  if (existsSync(resolve(repositoryRoot, path))) return true;
  const topLevel = path.split('/').filter(Boolean)[0];
  const stage = execFileSync('git', ['ls-files', '--stage', '--', topLevel], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  });
  return stage.startsWith('160000 ');
}

assert(schema.$id && schema.type === 'object', 'schema must identify an object contract');
assert(contract.$schema === './system.schema.json', 'contract must cite its adjacent schema');
assert(contract.schemaVersion === 'eden.engineering/v1', 'unsupported schemaVersion');
assert(contract.name === 'eden', 'system name must be eden');

const expectedHomes = ['product', 'architecture', 'engineering', 'agentExecution'];
assert(
  Object.keys(contract.homes).sort().join() === expectedHomes.sort().join(),
  'homes must name exactly the four canonical layers',
);
for (const path of Object.values(contract.homes)) {
  assert(typeof path === 'string' && path.endsWith('/'), `invalid home path: ${path}`);
  assert(
    isAvailableRepositoryPath(path),
    `home does not exist or belong to a registered submodule: ${path}`,
  );
}

const harnesses = new Map(contract.harnesses.map((harness) => [harness.id, harness.entrypoint]));
assert(harnesses.size === 2, 'exactly two harnesses are required');
assert(harnesses.get('claude') === 'CLAUDE.md', 'Claude entrypoint must be CLAUDE.md');
assert(harnesses.get('codex') === 'AGENTS.md', 'Codex entrypoint must be AGENTS.md');
for (const entrypoint of harnesses.values()) statSync(resolve(repositoryRoot, entrypoint));

const expectedProcesses = ['feature', 'ci', 'parallel', 'review', 'release'];
const processIDs = contract.processes.map((process) => process.id);
assert(new Set(processIDs).size === processIDs.length, 'process ids must be unique');
assert(processIDs.join() === expectedProcesses.join(), 'process vocabulary or order drifted');
for (const process of contract.processes) {
  assert(['planned', 'active'].includes(process.status), `invalid process status: ${process.id}`);
  assert(
    process.path === `docs/engineering/processes/${process.id}.md`,
    `non-canonical process path: ${process.id}`,
  );
  if (process.status === 'active') statSync(resolve(repositoryRoot, process.path));
}

console.log('engineering-system: OK');
