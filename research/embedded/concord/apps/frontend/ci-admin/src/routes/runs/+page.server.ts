import { listRuns } from '$lib/server/db';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => {
	const pipeline = url.searchParams.get('pipeline') || undefined;
	const verdict = url.searchParams.get('verdict') || undefined;
	const page = parseInt(url.searchParams.get('page') || '1');
	const { runs, total } = listRuns({ pipeline, verdict, limit: 50, offset: (page - 1) * 50 });

	return { runs, total, page, pipeline, verdict };
};
