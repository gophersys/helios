export type Pipeline = 'nightly' | 'weekly' | 'pr' | 'main' | 'release';
export type Verdict = 'pass' | 'fail' | 'error';
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface CiRun {
	id: string;
	pipeline: Pipeline;
	verdict: Verdict;
	branch: string;
	commitSha: string;
	durationSeconds: number;
	totalCost: number;
	totalIssues: number;
	severity: Severity;
	createdAt: string;
	stages?: CiStage[];
}

export interface CiStage {
	name: string;
	verdict: Verdict;
	severity: Severity;
	issues: number;
	cost: number;
	model: string;
}

export interface CiFinding {
	stage: string;
	file: string;
	severity: Severity;
	message: string;
}

export interface TrendPoint {
	date: string;
	issues: number;
	cost: number;
	passed: number;
	failed: number;
}

export interface Hotspot {
	file: string;
	appearances: number;
	stages: string[];
	severities: Severity[];
}
