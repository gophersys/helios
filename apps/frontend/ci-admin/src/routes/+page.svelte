<script lang="ts">
	import { CheckCircle, XCircle, DollarSign, Clock, TrendingUp, TrendingDown, Minus, Activity } from 'lucide-svelte';

	let { data } = $props();
	const { runs, trends, stats } = data;

	function formatDuration(seconds: number): string {
		const m = Math.floor(seconds / 60);
		const s = seconds % 60;
		return `${m}m ${s}s`;
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
	}

	// Sparkline from trend history
	function sparklinePath(data: { value: number }[], width = 120, height = 32): string {
		if (data.length < 2) return '';
		const max = Math.max(...data.map(d => d.value), 1);
		const points = data.map((d, i) => {
			const x = (i / (data.length - 1)) * width;
			const y = height - (d.value / max) * (height - 4);
			return `${x},${y}`;
		});
		return `M${points.join(' L')}`;
	}

	const issueSpark = sparklinePath(trends.history.map(h => ({ value: h.issues })));
	const costSpark = sparklinePath(trends.history.map(h => ({ value: h.cost })));

	const latestRun = runs[0];
</script>

<div class="space-y-6" style="animation: fade-in 0.2s ease-out;">
	<div>
		<h1 class="page-title">CI Overview</h1>
		<p class="page-subtitle">AI-powered code review and pipeline health</p>
	</div>

	<!-- Stat cards -->
	<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
		<div class="stat-card">
			<span class="stat-label">Runs (7d)</span>
			<span class="stat-value">{stats.totalRuns}</span>
			<span class="stat-change" style="color: var(--success)">{stats.passRate}% pass rate</span>
		</div>

		<div class="stat-card">
			<div class="flex items-center justify-between">
				<div>
					<span class="stat-label">Issues</span>
					<span class="stat-value">{stats.totalIssues}</span>
				</div>
				{#if issueSpark}
					<svg width="120" height="32" style="opacity: 0.6">
						<path d={issueSpark} fill="none" stroke="var(--accent)" stroke-width="1.5" />
					</svg>
				{/if}
			</div>
			<span class="stat-change" style="color: var(--text-tertiary)">
				{#if trends.issueDirection === 'rising'}
					<TrendingUp class="inline w-3 h-3" style="color: var(--error)" /> Rising
				{:else if trends.issueDirection === 'falling'}
					<TrendingDown class="inline w-3 h-3" style="color: var(--success)" /> Falling
				{:else}
					<Minus class="inline w-3 h-3" /> Stable
				{/if}
				&middot; avg {trends.issue7dAvg}/day
			</span>
		</div>

		<div class="stat-card">
			<div class="flex items-center justify-between">
				<div>
					<span class="stat-label">Cost (7d)</span>
					<span class="stat-value">${stats.totalCost.toFixed(2)}</span>
				</div>
				{#if costSpark}
					<svg width="120" height="32" style="opacity: 0.6">
						<path d={costSpark} fill="none" stroke="var(--info)" stroke-width="1.5" />
					</svg>
				{/if}
			</div>
			<span class="stat-change" style="color: var(--text-tertiary)">
				<DollarSign class="inline w-3 h-3" /> avg ${stats.totalRuns > 0 ? (stats.totalCost / stats.totalRuns).toFixed(2) : '0.00'}/run
			</span>
		</div>

		<div class="stat-card">
			<span class="stat-label">Latest Run</span>
			{#if latestRun}
				<div class="flex items-center gap-2">
					{#if latestRun.verdict === 'pass'}
						<CheckCircle class="w-5 h-5" style="color: var(--success)" />
						<span class="stat-value" style="color: var(--success)">Pass</span>
					{:else}
						<XCircle class="w-5 h-5" style="color: var(--error)" />
						<span class="stat-value" style="color: var(--error)">Fail</span>
					{/if}
				</div>
				<span class="stat-change" style="color: var(--text-tertiary)">
					<Clock class="inline w-3 h-3" /> {formatDuration(latestRun.duration_seconds)}
				</span>
			{:else}
				<div class="flex items-center gap-2">
					<Activity class="w-5 h-5" style="color: var(--text-tertiary)" />
					<span class="text-sm" style="color: var(--text-tertiary)">No runs yet</span>
				</div>
			{/if}
		</div>
	</div>

	<!-- Recent runs table -->
	{#if runs.length > 0}
		<div class="card">
			<div style="padding: 16px 20px; border-bottom: 1px solid var(--border)">
				<h2 style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary)">Recent Runs</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="table">
					<thead>
						<tr>
							<th>Date</th>
							<th>Pipeline</th>
							<th>Branch</th>
							<th>Verdict</th>
							<th>Issues</th>
							<th>Cost</th>
							<th>Duration</th>
						</tr>
					</thead>
					<tbody>
						{#each runs as run}
							<tr class="cursor-pointer" onclick={() => window.location.href = `/runs/${run.id}`}>
								<td style="font-size: 0.75rem; color: var(--text-secondary)">{formatDate(run.created_at)}</td>
								<td><span class="badge badge-neutral">{run.pipeline}</span></td>
								<td style="font-family: var(--font-mono); font-size: 0.75rem">{run.branch}@{run.commit_sha}</td>
								<td>
									{#if run.verdict === 'pass'}
										<span class="badge badge-success">Pass</span>
									{:else}
										<span class="badge badge-error">Fail</span>
									{/if}
								</td>
								<td style="color: {run.total_issues > 10 ? 'var(--error)' : 'var(--text-primary)'}; font-weight: 500">{run.total_issues}</td>
								<td style="color: var(--text-secondary)">${run.total_cost.toFixed(2)}</td>
								<td style="font-size: 0.75rem; color: var(--text-secondary)">{formatDuration(run.duration_seconds)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{:else}
		<div class="card card-md" style="text-align: center; padding: 48px 24px">
			<Activity class="w-10 h-10 mx-auto mb-3" style="color: var(--text-tertiary)" />
			<p style="color: var(--text-secondary); font-size: 0.875rem">No CI runs yet. Trigger a nightly or weekly pipeline to see data here.</p>
			<p style="color: var(--text-tertiary); font-size: 0.75rem; margin-top: 8px">POST to <code>/api/runs</code> to ingest results.</p>
		</div>
	{/if}
</div>
