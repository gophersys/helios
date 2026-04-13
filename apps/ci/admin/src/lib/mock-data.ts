import type { CiRun, TrendPoint, Hotspot } from './types';

export const mockRuns: CiRun[] = [
	{
		id: '1', pipeline: 'nightly', verdict: 'fail', branch: 'main', commitSha: 'a9a2a20',
		durationSeconds: 312, totalCost: 1.02, totalIssues: 33, severity: 'critical', createdAt: '2026-04-13T08:00:00Z',
		stages: [
			{ name: 'completeness', verdict: 'fail', severity: 'critical', issues: 4, cost: 0.35, model: 'claude-sonnet-4-6' },
			{ name: 'security', verdict: 'fail', severity: 'high', issues: 7, cost: 0.29, model: 'claude-sonnet-4-6' },
			{ name: 'blast-radius', verdict: 'pass', severity: 'info', issues: 16, cost: 0.27, model: 'claude-sonnet-4-6' },
			{ name: 'docs', verdict: 'fail', severity: 'critical', issues: 10, cost: 0.29, model: 'claude-sonnet-4-6' },
		]
	},
	{
		id: '2', pipeline: 'weekly', verdict: 'pass', branch: 'main', commitSha: 'b5aef2c',
		durationSeconds: 487, totalCost: 2.15, totalIssues: 8, severity: 'medium', createdAt: '2026-04-12T09:00:00Z',
		stages: [
			{ name: 'completeness', verdict: 'pass', severity: 'info', issues: 0, cost: 0.34, model: 'claude-sonnet-4-6' },
			{ name: 'security', verdict: 'pass', severity: 'info', issues: 0, cost: 0.28, model: 'claude-sonnet-4-6' },
			{ name: 'architecture', verdict: 'pass', severity: 'info', issues: 5, cost: 0.13, model: 'claude-sonnet-4-6' },
			{ name: 'docs', verdict: 'pass', severity: 'medium', issues: 3, cost: 0.29, model: 'claude-sonnet-4-6' },
		]
	},
	{
		id: '3', pipeline: 'nightly', verdict: 'pass', branch: 'main', commitSha: 'fd75759',
		durationSeconds: 245, totalCost: 0.87, totalIssues: 5, severity: 'low', createdAt: '2026-04-11T08:00:00Z',
		stages: [
			{ name: 'completeness', verdict: 'pass', severity: 'info', issues: 0, cost: 0.34, model: 'claude-sonnet-4-6' },
			{ name: 'security', verdict: 'pass', severity: 'low', issues: 2, cost: 0.28, model: 'claude-sonnet-4-6' },
			{ name: 'blast-radius', verdict: 'pass', severity: 'info', issues: 3, cost: 0.25, model: 'claude-sonnet-4-6' },
		]
	},
];

export const mockTrends: TrendPoint[] = [
	{ date: '2026-04-07', issues: 12, cost: 0.95, passed: 3, failed: 1 },
	{ date: '2026-04-08', issues: 8, cost: 0.88, passed: 4, failed: 0 },
	{ date: '2026-04-09', issues: 15, cost: 1.10, passed: 2, failed: 2 },
	{ date: '2026-04-10', issues: 10, cost: 0.92, passed: 3, failed: 1 },
	{ date: '2026-04-11', issues: 5, cost: 0.87, passed: 4, failed: 0 },
	{ date: '2026-04-12', issues: 8, cost: 2.15, passed: 4, failed: 0 },
	{ date: '2026-04-13', issues: 33, cost: 1.02, passed: 1, failed: 3 },
];

export const mockHotspots: Hotspot[] = [
	{ file: 'apps/frontend/app/src/lib/types/models.ts', appearances: 5, stages: ['completeness', 'docs'], severities: ['critical', 'medium'] },
	{ file: 'apps/backend/http-api/src/api/v2/docs.py', appearances: 4, stages: ['completeness', 'docs'], severities: ['medium'] },
	{ file: 'apps/backend/http-api/tests/contracts/', appearances: 3, stages: ['completeness'], severities: ['critical', 'medium'] },
	{ file: 'apps/backend/build-service/src/app.py', appearances: 3, stages: ['security'], severities: ['high'] },
	{ file: 'apps/backend/http-api/src/api/v2/assets/asset_sets.py', appearances: 2, stages: ['completeness', 'security'], severities: ['medium', 'low'] },
];
