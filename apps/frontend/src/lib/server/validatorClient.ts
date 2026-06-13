// The validator client — the seam between the SvelteKit server and the projection
// source of truth (ADR-0015 §2). It shells out to the prebuilt documentvalidator
// binary (apps/frontend/.eden/documentvalidator, built by ctl.sh), falling back to
// `go run` from tools/documentvalidator when the binary is absent (a fresh
// checkout that has not run a build verb yet). Results are held in a small
// in-memory cache with a 5-second TTL so a page that fetches projection + links +
// validation for the same project does not invoke the CLI three times per click.
//
// This is the frozen seam ADR-0015 §2 names: a Go backend slice replaces the
// shell-out later, but the projection contract it speaks does not change, so the
// swap is mechanical and confined to this file.

import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { promisify } from 'node:util';

import { repositoryRoot } from './repository';

const execFileAsync = promisify(execFile);

// The prebuilt binary location (ctl.sh builds it into .eden/, gitignored) and the
// Go source directory for the fallback invocation.
const binaryPath = join(repositoryRoot(), 'apps', 'frontend', '.eden', 'documentvalidator');
const validatorSourceDirectory = join(repositoryRoot(), 'tools', 'documentvalidator');

// A raised error the route layer can recognize: the validator could not be
// invoked at all (neither binary nor go), so the surface should render an
// instructive setup message rather than a generic failure.
export class ValidatorUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidatorUnavailableError';
  }
}

// The exit code documentvalidator returns when it found violations (vs. a clean
// run or a usage/IO error). On this code stdout is still valid JSON — the report
// with ok:false — so the caller keeps it rather than treating it as a failure.
const EXIT_CODE_VIOLATIONS = 1;

interface InvocationResult {
  readonly stdout: string;
  // True when the process exited with the violations code (1). The report is still
  // present on stdout; this flags that validation was non-clean.
  readonly violationsExit: boolean;
}

// Resolve the command + leading args for an invocation: the prebuilt binary if it
// exists, else `go run ./cmd/documentvalidator` from the source directory.
function resolveCommand(): { command: string; baseArguments: string[]; cwd: string } {
  if (existsSync(binaryPath)) {
    return { command: binaryPath, baseArguments: [], cwd: repositoryRoot() };
  }
  if (existsSync(validatorSourceDirectory)) {
    return {
      command: 'go',
      baseArguments: ['run', './cmd/documentvalidator'],
      cwd: validatorSourceDirectory,
    };
  }
  throw new ValidatorUnavailableError(
    `the documentvalidator is unavailable: no prebuilt binary at ${binaryPath} and no Go source at ${validatorSourceDirectory}. ` +
      `Build it with \`bash apps/frontend/ctl.sh build\` (or any dev/build verb), which compiles the binary into .eden/.`,
  );
}

// Run one validator invocation. The verb-specific arguments (e.g. ['project',
// dir] or ['validate', dir, '--json']) are appended to the resolved base. A
// non-zero exit other than the violations code is a real failure and rethrows.
async function invoke(verbArguments: string[]): Promise<InvocationResult> {
  const { command, baseArguments, cwd } = resolveCommand();
  const allArguments = [...baseArguments, ...verbArguments];
  try {
    const { stdout } = await execFileAsync(command, allArguments, {
      cwd,
      // Projections of a full corpus run to tens of kilobytes; give generous room.
      maxBuffer: 32 * 1024 * 1024,
      // A `go run` cold compile can take a few seconds the first time; the prebuilt
      // binary is near-instant. Bound it so a hung child cannot wedge a request.
      timeout: 60_000,
    });
    return { stdout, violationsExit: false };
  } catch (error) {
    // execFile rejects on any non-zero exit. The validate verb exits 1 with a
    // valid JSON report when it finds violations — keep that stdout and flag it.
    const failure = error as { code?: number; stdout?: string; message?: string };
    if (failure.code === EXIT_CODE_VIOLATIONS && typeof failure.stdout === 'string') {
      return { stdout: failure.stdout, violationsExit: true };
    }
    if (command === 'go' && /ENOENT|not found/i.test(failure.message ?? '')) {
      throw new ValidatorUnavailableError(
        `the documentvalidator binary is absent and the \`go\` toolchain is not on PATH, so the fallback cannot run. ` +
          `Build the binary with \`bash apps/frontend/ctl.sh build\`.`,
      );
    }
    throw new Error(
      `documentvalidator ${allArguments.join(' ')} failed (exit ${failure.code ?? 'unknown'}): ${failure.message ?? 'no message'}`,
    );
  }
}

// ── the 5-second TTL cache ───────────────────────────────────────────────────
// Keyed by the full argument list. Each entry holds the parsed value and the
// timestamp it was produced; entries past their TTL are recomputed on read.

const CACHE_TTL_MILLISECONDS = 5_000;

interface CacheEntry {
  readonly value: unknown;
  readonly producedAt: number;
}

const cache = new Map<string, CacheEntry>();

async function cached<T>(key: string, produce: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const entry = cache.get(key);
  if (entry && now - entry.producedAt < CACHE_TTL_MILLISECONDS) {
    return entry.value as T;
  }
  const value = await produce();
  cache.set(key, { value, producedAt: now });
  return value;
}

// ── the document projection (NDJSON → array) ─────────────────────────────────

// The projected document shape (doc 11 §5): the validator emits {meta, data,
// sections} per document. data and sections vary by type, so they are kept open.
export interface DocumentMeta {
  readonly id: string;
  readonly type: string;
  readonly schema_version?: string;
  readonly project?: string;
  readonly status: string;
  readonly version: number;
  readonly created?: string;
  readonly updated?: string;
  readonly authors?: Array<Record<string, unknown>>;
  readonly links?: Record<string, unknown>;
  readonly source?: Array<Record<string, unknown>>;
  readonly [key: string]: unknown;
}

export interface ProjectedDocument {
  readonly meta: DocumentMeta;
  readonly data: Record<string, unknown>;
  readonly sections: Record<string, string>;
}

// Run `project <dir>` and parse the NDJSON stream into an array of documents.
export async function projectDocuments(directory: string): Promise<ProjectedDocument[]> {
  return cached(`project:${directory}`, async () => {
    const { stdout } = await invoke(['project', directory]);
    const documents: ProjectedDocument[] = [];
    for (const line of stdout.split('\n')) {
      const trimmed = line.trim();
      if (trimmed === '') continue;
      documents.push(JSON.parse(trimmed) as ProjectedDocument);
    }
    return documents;
  });
}

// ── the link graph ───────────────────────────────────────────────────────────

// One typed edge of the corpus graph (doc 11 §3): always authored upstream, so
// reverse edges (backlinks) are derived by the consumer, never read here.
export interface LinkEdge {
  readonly file: string;
  readonly from: string;
  readonly type: string;
  readonly to: string;
}

export async function projectLinks(directory: string): Promise<LinkEdge[]> {
  return cached(`links:${directory}`, async () => {
    const { stdout } = await invoke(['links', directory, '--json']);
    return JSON.parse(stdout) as LinkEdge[];
  });
}

// ── validation + coverage ─────────────────────────────────────────────────────

// A single diagnostic from the validator (a shape/traceability violation, or a T6
// coverage-gap entry). The shape is identical for both lists.
export interface Diagnostic {
  readonly file: string;
  readonly documentId?: string;
  readonly rule?: string;
  readonly message: string;
}

// The validate report. `ok` mirrors the validator's own field (no violations);
// `violationsExit` records that the process exited non-zero — they agree, but both
// are surfaced so the route can flag a non-clean run explicitly per the task.
export interface ValidationReport {
  readonly violations: Diagnostic[];
  readonly coverage: Diagnostic[];
  readonly ok: boolean;
  readonly violationsExit: boolean;
}

export async function validateDocuments(directory: string): Promise<ValidationReport> {
  return cached(`validate:${directory}`, async () => {
    const { stdout, violationsExit } = await invoke(['validate', directory, '--json']);
    const report = JSON.parse(stdout) as {
      violations: Diagnostic[];
      coverage: Diagnostic[];
      ok: boolean;
    };
    return {
      violations: report.violations ?? [],
      coverage: report.coverage ?? [],
      ok: report.ok,
      violationsExit,
    };
  });
}
