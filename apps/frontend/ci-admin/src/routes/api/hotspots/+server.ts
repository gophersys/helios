import { json } from '@sveltejs/kit';
import { getHotspots } from '$lib/server/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url }) => {
	const limit = parseInt(url.searchParams.get('limit') || '20');
	const hotspots = getHotspots(limit);

	// Parse comma-separated strings into arrays
	const parsed = hotspots.map(h => ({
		file: h.file,
		appearances: h.appearances,
		stages: h.stages ? h.stages.split(',') : [],
		severities: h.severities ? h.severities.split(',') : [],
	}));

	return json({ data: parsed });
};
