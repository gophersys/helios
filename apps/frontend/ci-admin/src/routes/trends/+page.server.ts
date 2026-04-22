import { getTrends } from '$lib/server/db';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const trends = getTrends(14);
	return { trends };
};
