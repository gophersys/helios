// GET /api/projects — the registry of openable projects (slug, title, directory).
// The directory is surfaced so a debugging operator can see which corpus a slug
// resolves to; the UI uses slug + title.

import { json } from '@sveltejs/kit';

import { projectRegistry } from '$lib/server/repository';

export const prerender = false;

export function GET() {
  return json(projectRegistry());
}
