import Database from 'better-sqlite3';
import { v4 as uuidv4 } from 'uuid';
import path from 'node:path';
import fs from 'node:fs';

const DATA_DIR = process.env.CI_DATA_DIR || path.join(process.cwd(), 'data');
const DB_PATH = path.join(DATA_DIR, 'ci.db');

// Ensure data directory exists
fs.mkdirSync(DATA_DIR, { recursive: true });

let _db: Database.Database | null = null;

function getDb(): Database.Database {
	if (!_db) {
		_db = new Database(DB_PATH);
		_db.pragma('journal_mode = WAL');
		_db.pragma('foreign_keys = ON');
		migrate(_db);
	}
	return _db;
}

function migrate(db: Database.Database): void {
	db.exec(`
		CREATE TABLE IF NOT EXISTS runs (
			id TEXT PRIMARY KEY,
			pipeline TEXT NOT NULL,
			verdict TEXT NOT NULL DEFAULT 'pass',
			branch TEXT NOT NULL DEFAULT 'unknown',
			commit_sha TEXT NOT NULL DEFAULT 'unknown',
			duration_seconds INTEGER NOT NULL DEFAULT 0,
			total_cost REAL NOT NULL DEFAULT 0,
			total_issues INTEGER NOT NULL DEFAULT 0,
			severity TEXT NOT NULL DEFAULT 'info',
			created_at TEXT NOT NULL DEFAULT (datetime('now'))
		);

		CREATE TABLE IF NOT EXISTS stages (
			id TEXT PRIMARY KEY,
			run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
			name TEXT NOT NULL,
			verdict TEXT NOT NULL DEFAULT 'pass',
			severity TEXT NOT NULL DEFAULT 'info',
			issues INTEGER NOT NULL DEFAULT 0,
			cost REAL NOT NULL DEFAULT 0,
			model TEXT NOT NULL DEFAULT 'unknown',
			duration_seconds INTEGER NOT NULL DEFAULT 0,
			summary TEXT NOT NULL DEFAULT '',
			logs TEXT NOT NULL DEFAULT '',
			created_at TEXT NOT NULL DEFAULT (datetime('now'))
		);

		CREATE TABLE IF NOT EXISTS findings (
			id TEXT PRIMARY KEY,
			run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
			stage TEXT NOT NULL,
			file TEXT NOT NULL DEFAULT '',
			severity TEXT NOT NULL DEFAULT 'info',
			message TEXT NOT NULL DEFAULT '',
			created_at TEXT NOT NULL DEFAULT (datetime('now'))
		);

		CREATE INDEX IF NOT EXISTS idx_stages_run_id ON stages(run_id);
		CREATE INDEX IF NOT EXISTS idx_findings_run_id ON findings(run_id);
		CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
		CREATE INDEX IF NOT EXISTS idx_findings_file ON findings(file);
	`);
}

// ── Queries ─────────────────────────────────────────────────

export function listRuns(opts: {
	pipeline?: string;
	verdict?: string;
	limit?: number;
	offset?: number;
} = {}): { runs: RunRow[]; total: number } {
	const db = getDb();
	const where: string[] = [];
	const params: Record<string, string | number> = {};

	if (opts.pipeline) {
		where.push('pipeline = :pipeline');
		params.pipeline = opts.pipeline;
	}
	if (opts.verdict) {
		where.push('verdict = :verdict');
		params.verdict = opts.verdict;
	}

	const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';
	const limit = opts.limit ?? 50;
	const offset = opts.offset ?? 0;

	const total = db.prepare(`SELECT COUNT(*) as count FROM runs ${whereClause}`).get(params) as { count: number };
	const runs = db.prepare(`SELECT * FROM runs ${whereClause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset`).all({ ...params, limit, offset }) as RunRow[];

	return { runs, total: total.count };
}

export function getRun(id: string): RunDetail | null {
	const db = getDb();
	const run = db.prepare('SELECT * FROM runs WHERE id = ?').get(id) as RunRow | undefined;
	if (!run) return null;

	const stages = db.prepare('SELECT * FROM stages WHERE run_id = ? ORDER BY name').all(id) as StageRow[];
	const findings = db.prepare('SELECT * FROM findings WHERE run_id = ? ORDER BY severity DESC, file').all(id) as FindingRow[];

	return { ...run, stages, findings };
}

export function createRun(data: CreateRunInput): string {
	const db = getDb();
	const id = uuidv4();

	// Compute totals from stages
	let totalCost = 0;
	let totalIssues = 0;
	let maxSeverity = 'info';
	let verdict: 'pass' | 'fail' = 'pass';
	const sevRank: Record<string, number> = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };

	for (const stage of data.stages || []) {
		totalCost += stage.cost_usd || 0;
		totalIssues += stage.issues || 0;
		if (stage.verdict === 'fail') verdict = 'fail';
		if ((sevRank[stage.severity] || 0) > (sevRank[maxSeverity] || 0)) {
			maxSeverity = stage.severity;
		}
	}

	const insertRun = db.prepare(`
		INSERT INTO runs (id, pipeline, verdict, branch, commit_sha, duration_seconds, total_cost, total_issues, severity, created_at)
		VALUES (:id, :pipeline, :verdict, :branch, :commitSha, :duration, :cost, :issues, :severity, datetime('now'))
	`);

	const insertStage = db.prepare(`
		INSERT INTO stages (id, run_id, name, verdict, severity, issues, cost, model, duration_seconds, summary, logs, created_at)
		VALUES (:id, :runId, :name, :verdict, :severity, :issues, :cost, :model, :duration, :summary, :logs, datetime('now'))
	`);

	const insertFinding = db.prepare(`
		INSERT INTO findings (id, run_id, stage, file, severity, message, created_at)
		VALUES (:id, :runId, :stage, :file, :severity, :message, datetime('now'))
	`);

	const transaction = db.transaction(() => {
		insertRun.run({
			id,
			pipeline: data.pipeline,
			verdict,
			branch: data.branch || 'unknown',
			commitSha: data.commitSha || 'unknown',
			duration: data.durationSeconds || 0,
			cost: totalCost,
			issues: totalIssues,
			severity: maxSeverity,
		});

		for (const stage of data.stages || []) {
			const stageId = uuidv4();
			insertStage.run({
				id: stageId,
				runId: id,
				name: stage.stage || stage.name || 'unknown',
				verdict: stage.verdict || 'pass',
				severity: stage.severity || 'info',
				issues: stage.issues || 0,
				cost: stage.cost_usd || stage.cost || 0,
				model: stage.model || 'unknown',
				duration: stage.duration_seconds || 0,
				summary: stage.summary || '',
				logs: stage.logs || '',
			});

			for (const finding of stage.findings || []) {
				insertFinding.run({
					id: uuidv4(),
					runId: id,
					stage: stage.stage || stage.name || 'unknown',
					file: finding.file || '',
					severity: finding.severity || 'info',
					message: finding.message || '',
				});
			}
		}
	});

	transaction();
	return id;
}

export function getTrends(days: number = 14): TrendData {
	const db = getDb();

	const history = db.prepare(`
		SELECT
			date(created_at) as date,
			SUM(total_issues) as issues,
			SUM(total_cost) as cost,
			SUM(CASE WHEN verdict = 'pass' THEN 1 ELSE 0 END) as passed,
			SUM(CASE WHEN verdict = 'fail' THEN 1 ELSE 0 END) as failed
		FROM runs
		WHERE created_at >= datetime('now', :days)
		GROUP BY date(created_at)
		ORDER BY date ASC
	`).all({ days: `-${days} days` }) as TrendPoint[];

	const avgIssues = history.length ? history.reduce((s, h) => s + (h.issues || 0), 0) / history.length : 0;
	const avgCost = history.length ? history.reduce((s, h) => s + (h.cost || 0), 0) / history.length : 0;
	const latest = history[history.length - 1];

	let issueDirection: 'rising' | 'falling' | 'stable' = 'stable';
	let costDirection: 'rising' | 'falling' | 'stable' = 'stable';

	if (latest && avgIssues > 0) {
		if (latest.issues > avgIssues * 1.2) issueDirection = 'rising';
		else if (latest.issues < avgIssues * 0.8) issueDirection = 'falling';
	}
	if (latest && avgCost > 0) {
		if (latest.cost > avgCost * 1.3) costDirection = 'rising';
		else if (latest.cost < avgCost * 0.7) costDirection = 'falling';
	}

	// Severity distribution across all recent runs
	const sevDist = db.prepare(`
		SELECT severity, COUNT(*) as count
		FROM findings
		WHERE run_id IN (SELECT id FROM runs WHERE created_at >= datetime('now', :days))
		GROUP BY severity
	`).all({ days: `-${days} days` }) as { severity: string; count: number }[];

	const severityDistribution: Record<string, number> = {};
	for (const s of sevDist) {
		severityDistribution[s.severity] = s.count;
	}

	return {
		history,
		issueDirection,
		costDirection,
		issue7dAvg: Math.round(avgIssues * 10) / 10,
		cost7dAvg: Math.round(avgCost * 10000) / 10000,
		severityDistribution,
	};
}

export function getHotspots(limit: number = 20): HotspotRow[] {
	const db = getDb();
	return db.prepare(`
		SELECT
			file,
			COUNT(*) as appearances,
			GROUP_CONCAT(DISTINCT stage) as stages,
			GROUP_CONCAT(DISTINCT severity) as severities
		FROM findings
		WHERE file != ''
		GROUP BY file
		ORDER BY appearances DESC
		LIMIT :limit
	`).all({ limit }) as HotspotRow[];
}

// ── Types ───────────────────────────────────────────────────

export interface RunRow {
	id: string;
	pipeline: string;
	verdict: string;
	branch: string;
	commit_sha: string;
	duration_seconds: number;
	total_cost: number;
	total_issues: number;
	severity: string;
	created_at: string;
}

export interface StageRow {
	id: string;
	run_id: string;
	name: string;
	verdict: string;
	severity: string;
	issues: number;
	cost: number;
	model: string;
	duration_seconds: number;
	summary: string;
	logs: string;
	created_at: string;
}

export interface FindingRow {
	id: string;
	run_id: string;
	stage: string;
	file: string;
	severity: string;
	message: string;
	created_at: string;
}

export interface RunDetail extends RunRow {
	stages: StageRow[];
	findings: FindingRow[];
}

export interface CreateRunInput {
	pipeline: string;
	branch?: string;
	commitSha?: string;
	durationSeconds?: number;
	stages?: Array<{
		stage?: string;
		name?: string;
		verdict?: string;
		severity?: string;
		issues?: number;
		cost_usd?: number;
		cost?: number;
		model?: string;
		duration_seconds?: number;
		summary?: string;
		logs?: string;
		findings?: Array<{
			file?: string;
			severity?: string;
			message?: string;
		}>;
	}>;
}

export interface TrendPoint {
	date: string;
	issues: number;
	cost: number;
	passed: number;
	failed: number;
}

export interface TrendData {
	history: TrendPoint[];
	issueDirection: 'rising' | 'falling' | 'stable';
	costDirection: 'rising' | 'falling' | 'stable';
	issue7dAvg: number;
	cost7dAvg: number;
	severityDistribution: Record<string, number>;
}

export interface HotspotRow {
	file: string;
	appearances: number;
	stages: string;
	severities: string;
}
