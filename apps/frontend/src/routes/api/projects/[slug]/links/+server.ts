// GET /api/projects/[slug]/links — the typed link-edge list (the corpus graph,
// doc 11 §3). Edges are authored upstream-only; the consumer derives backlinks.

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

import { projectLinks } from '$lib/server/validatorClient';
import { requireProject, withValidator } from '../resolveProject';

export const prerender = false;

export const GET: RequestHandler = async ({ params }) => {
  const project = requireProject(params.slug);
  const links = await withValidator(() => projectLinks(project.directory));
  return json(links);
};
