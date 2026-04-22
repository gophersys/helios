<script lang="ts">
	import { TrendingUp, TrendingDown, Minus } from 'lucide-svelte';

	let { data } = $props();
	const { trends } = data;

	const totalPassed = trends.history.reduce((s: number, h: any) => s + (h.passed || 0), 0);
	const totalFailed = trends.history.reduce((s: number, h: any) => s + (h.failed || 0), 0);
	const passRate = (totalPassed + totalFailed) > 0 ? Math.round(totalPassed / (totalPassed + totalFailed) * 100) : 0;

	// Bar chart dimensions
	const maxIssues = Math.max(...trends.history.map((h: any) => h.issues || 0), 1);
	const barWidth = 40;
	const barGap = 8;
	const chartHeight = 160;
	const chartWidth = Math.max(trends.history.length * (barWidth + barGap), 200);

	// Severity entries sorted by rank
	const sevOrder = ['critical', 'high', 'medium', 'low', 'info'];
	const sevEntries = sevOrder
		.filter(s => (trends.severityDistribution[s] || 0) > 0)
		.map(s => ({ severity: s, count: trends.severityDistribution[s] || 0 }));
	const sevTotal = sevEntries.reduce((s, e) => s + e.count, 0) || 1;
</script>

<div class="space-y-6" style="animation: fade-in 0.2s ease-out;">
	<div>
		<h1 class="page-title">Trends</h1>
		<p class="page-subtitle">Issue and cost trends over the last 14 days</p>
	</div>

	<!-- Direction indicators -->
	<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
		<div class="stat-card">
			<span class="stat-label">Issue Trend</span>
			<div class="flex items-center gap-2">
				{#if trends.issueDirection === 'rising'}
					<TrendingUp class="w-5 h-5" style="color: var(--error)" />
					<span class="stat-value" style="color: var(--error)">Rising</span>
				{:else if trends.issueDirection === 'falling'}
					<TrendingDown class="w-5 h-5" style="color: var(--success)" />
					<span class="stat-value" style="color: var(--success)">Falling</span>
				{:else}
					<Minus class="w-5 h-5" style="color: var(--text-tertiary)" />
					<span class="stat-value">Stable</span>
				{/if}
			</div>
			<span class="stat-change" style="color: var(--text-tertiary)">avg {trends.issue7dAvg} issues/day</span>
		</div>

		<div class="stat-card">
			<span class="stat-label">Cost Trend</span>
			<div class="flex items-center gap-2">
				{#if trends.costDirection === 'rising'}
					<TrendingUp class="w-5 h-5" style="color: var(--warning)" />
					<span class="stat-value" style="color: var(--warning)">Rising</span>
				{:else if trends.costDirection === 'falling'}
					<TrendingDown class="w-5 h-5" style="color: var(--success)" />
					<span class="stat-value" style="color: var(--success)">Falling</span>
				{:else}
					<Minus class="w-5 h-5" style="color: var(--text-tertiary)" />
					<span class="stat-value">Stable</span>
				{/if}
			</div>
			<span class="stat-change" style="color: var(--text-tertiary)">avg ${trends.cost7dAvg}/run</span>
		</div>

		<div class="stat-card">
			<span class="stat-label">Pass Rate</span>
			<span class="stat-value">{passRate}%</span>
			<span class="stat-change" style="color: var(--text-tertiary)">{totalPassed} passed / {totalFailed} failed</span>
		</div>
	</div>

	<!-- Bar chart -->
	{#if trends.history.length > 0}
		<div class="card card-md">
			<h3 style="font-size: 0.875rem; font-weight: 600; margin-bottom: 16px">Issues per Day</h3>
			<div class="overflow-x-auto">
				<svg width={chartWidth} height={chartHeight + 40} style="width: 100%;" viewBox="0 0 {chartWidth} {chartHeight + 40}">
					{#each trends.history as point, i}
						{@const barH = ((point.issues || 0) / maxIssues) * chartHeight}
						{@const x = i * (barWidth + barGap)}
						<rect
							{x} y={chartHeight - barH} width={barWidth} height={barH}
							rx="4" fill="var(--accent)" opacity="0.8"
						/>
						<text x={x + barWidth / 2} y={chartHeight + 16} text-anchor="middle"
							fill="var(--text-tertiary)" font-size="10">
							{new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
						</text>
						<text x={x + barWidth / 2} y={chartHeight - barH - 4} text-anchor="middle"
							fill="var(--text-secondary)" font-size="11" font-weight="500">
							{point.issues}
						</text>
					{/each}
				</svg>
			</div>
		</div>
	{/if}

	<!-- Severity distribution -->
	{#if sevEntries.length > 0}
		<div class="card card-md">
			<h3 style="font-size: 0.875rem; font-weight: 600; margin-bottom: 16px">Severity Distribution</h3>
			<div class="space-y-3">
				{#each sevEntries as entry}
					{@const pct = (entry.count / sevTotal) * 100}
					<div class="flex items-center gap-3">
						<span style="width: 64px; font-size: 0.75rem; font-weight: 500; color: var(--text-secondary); text-transform: capitalize">{entry.severity}</span>
						<div class="flex-1" style="height: 24px; background: var(--surface-2); border-radius: 6px; overflow: hidden">
							<div
								style="height: 100%; border-radius: 6px; width: {pct}%; background: {entry.severity === 'critical' ? 'var(--error)' : entry.severity === 'high' ? 'var(--warning)' : entry.severity === 'medium' ? 'var(--info)' : 'var(--surface-3)'}; transition: width 0.3s"
							></div>
						</div>
						<span style="width: 32px; font-size: 0.75rem; color: var(--text-secondary); text-align: right">{entry.count}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
