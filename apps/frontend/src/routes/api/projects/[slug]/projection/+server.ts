// GET /api/projects/[slug]/projection — the document corpus as a JSON array of
// {meta, data, sections} projections (doc 11 §5). The validator emits NDJSON; the
// client parses it into the array this route returns.

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

import { projectDocuments } from '$lib/server/validatorClient';
import { requireProject, withValidator } from '../resolveProject';

export const prerender = false;

export const GET: RequestHandler = async ({ params }) => {
  const project = requireProject(params.slug);
  const documents = await withValidator(() => projectDocuments(project.directory));
  return json(documents);
};
