// Repository-root resolution and the projects registry.
//
// The document workspace serves projections from on-disk document corpora. The
// projection source of truth is the documentvalidator CLI (ADR-0015 §2), which
// reads a directory of documents. This module resolves where those directories
// live: it walks up from the app directory to the repository root (the directory
// that contains schemas/document/v1), so the app works regardless of the cwd the
// server was launched from.

import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// The marker that identifies the repository root: the document-schema directory
// (schemas/document/v1) is present only at the monorepo root, so finding it is an
// unambiguous anchor (it is also where the validator's default schema dir lives).
const REPOSITORY_ROOT_MARKER = join('schemas', 'document', 'v1');

// Walk up from a starting directory until a directory containing the marker is
// found. Returns the repository root, or throws an instructive error naming where
// it searched — a missing root is a deployment misconfiguration, not a runtime
// condition the UI should silently absorb.
function findRepositoryRoot(startDirectory: string): string {
  let current = startDirectory;
  const visited: string[] = [];
  for (;;) {
    visited.push(current);
    if (existsSync(join(current, REPOSITORY_ROOT_MARKER))) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      throw new Error(
        `could not locate the repository root: no ancestor of ${startDirectory} contains ${REPOSITORY_ROOT_MARKER} (searched ${visited.join(', ')})`,
      );
    }
    current = parent;
  }
}

// This module file lives at apps/frontend/src/lib/server/repository.ts (in source)
// or its build equivalent; either way an ancestor is the repository root, so the
// upward walk resolves it. The result is memoized — the root never moves during a
// server's lifetime.
const moduleDirectory = dirname(fileURLToPath(import.meta.url));
let memoizedRepositoryRoot: string | null = null;

export function repositoryRoot(): string {
  if (memoizedRepositoryRoot === null) {
    memoizedRepositoryRoot = findRepositoryRoot(moduleDirectory);
  }
  return memoizedRepositoryRoot;
}

// A project the workspace can open: a stable slug, a human title, and the absolute
// directory of its document corpus.
export interface ProjectEntry {
  readonly slug: string;
  readonly title: string;
  readonly directory: string;
}

// The v0 registry. Eden-the-project (documents/) is project #1 — the dogfood
// corpus; the linkbox worked example is the schema's reference instance. Both are
// resolved relative to the repository root so the registry is location-independent.
export function projectRegistry(): ProjectEntry[] {
  const root = repositoryRoot();
  return [
    {
      slug: 'eden',
      title: 'Eden (project #1)',
      directory: join(root, 'documents'),
    },
    {
      slug: 'linkbox',
      title: 'Linkbox (worked example)',
      directory: join(root, 'schemas', 'document', 'v1', 'examples', 'linkbox'),
    },
  ];
}

// Resolve a slug to its registry entry, or null when the slug is unknown — the
// route layer turns null into a 404, never a thrown 500.
export function projectForSlug(slug: string): ProjectEntry | null {
  return projectRegistry().find((entry) => entry.slug === slug) ?? null;
}
