import { json } from '@sveltejs/kit';
import { listRuns, createRun } from '$lib/server/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url }) => {
	const pipeline = url.searchParams.get('pipeline') || undefined;
	const verdict = url.searchParams.get('verdict') || undefined;
	const limit = parseInt(url.searchParams.get('limit') || '50');
	const page = parseInt(url.searchParams.get('page') || '1');
	const offset = (page - 1) * limit;

	const { runs, total } = listRuns({ pipeline, verdict, limit, offset });

	return json({
		data: runs,
		pagination: { page, limit, total, pages: Math.ceil(total / limit) }
	});
};

export const POST: RequestHandler = async ({ request }) => {
	try {
		const body = await request.json();
		const id = createRun(body);
		return json({ id }, { status: 201 });
	} catch (err) {
		const message = err instanceof Error ? err.message : 'Unknown error';
		return json({ error: message }, { status: 400 });
	}
};
