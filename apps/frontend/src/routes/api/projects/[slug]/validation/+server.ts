// GET /api/projects/[slug]/validation — the validate report (shape + traceability
// violations, T6 coverage gaps). A non-zero validator exit (violations found)
// still yields a JSON report; the client returns it with violationsExit:true so
// the surface can flag a non-clean run rather than erroring.

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

import { validateDocuments } from '$lib/server/validatorClient';
import { requireProject, withValidator } from '../resolveProject';

export const prerender = false;

export const GET: RequestHandler = async ({ params }) => {
  const project = requireProject(params.slug);
  const report = await withValidator(() => validateDocuments(project.directory));
  return json(report);
};
