// Shared resolution for the per-slug API endpoints: turn a slug into its registry
// entry or raise a 404, and turn a ValidatorUnavailableError into a 503 with an
// instructive body (the validator is a deployment dependency, not a user error).

import { error } from '@sveltejs/kit';

import { projectForSlug, type ProjectEntry } from '$lib/server/repository';
import { ValidatorUnavailableError } from '$lib/server/validatorClient';

// Resolve the slug param to a project, raising a 404 SvelteKit error when unknown.
export function requireProject(slug: string): ProjectEntry {
  const project = projectForSlug(slug);
  if (!project) {
    throw error(404, `no project registered for slug "${slug}"`);
  }
  return project;
}

// Run a validator-backed producer, mapping a missing validator to a 503 whose
// message tells the operator how to build it. Other errors propagate to
// SvelteKit's default 500 handling.
export async function withValidator<T>(produce: () => Promise<T>): Promise<T> {
  try {
    return await produce();
  } catch (caught) {
    if (caught instanceof ValidatorUnavailableError) {
      throw error(503, caught.message);
    }
    throw caught;
  }
}
