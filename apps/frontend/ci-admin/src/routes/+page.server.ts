import { listRuns, getTrends } from '$lib/server/db';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const { runs } = listRuns({ limit: 10 });
	const trends = getTrends(7);

	const totalRuns = runs.length;
	const passedRuns = runs.filter(r => r.verdict === 'pass').length;
	const passRate = totalRuns > 0 ? Math.round((passedRuns / totalRuns) * 100) : 0;
	const totalIssues = runs.reduce((s, r) => s + r.total_issues, 0);
	const totalCost = runs.reduce((s, r) => s + r.total_cost, 0);

	return {
		runs,
		trends,
		stats: { totalRuns, passedRuns, passRate, totalIssues, totalCost }
	};
};
