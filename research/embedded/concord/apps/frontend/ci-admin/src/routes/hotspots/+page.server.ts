import { getHotspots } from '$lib/server/db';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const raw = getHotspots(20);
	const hotspots = raw.map(h => ({
		file: h.file,
		appearances: h.appearances,
		stages: h.stages ? h.stages.split(',') : [],
		severities: h.severities ? h.severities.split(',') : [],
	}));
	return { hotspots };
};
