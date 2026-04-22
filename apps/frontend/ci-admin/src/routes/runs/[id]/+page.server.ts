import { error } from '@sveltejs/kit';
import { getRun } from '$lib/server/db';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const run = getRun(params.id);
	if (!run) {
		throw error(404, 'Run not found');
	}
	return { run };
};
