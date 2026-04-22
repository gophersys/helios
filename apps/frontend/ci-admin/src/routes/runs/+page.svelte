<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { CheckCircle, XCircle, Clock, Filter } from 'lucide-svelte';
	import { stageClass, stageName } from '$lib/stage-colors';

	let { data } = $props();

	function formatDuration(s: number): string {
		return `${Math.floor(s / 60)}m ${s % 60}s`;
	}
	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
	}

	function applyFilter(key: string, value: string) {
		const url = new URL($page.url);
		if (value) {
			url.searchParams.set(key, value);
		} else {
			url.searchParams.delete(key);
		}
		url.searchParams.delete('page');
		goto(url.toString(), { replaceState: true, invalidateAll: true });
	}
</script>

<div class="space-y-5" style="animation: fade-in 0.2s ease-out;">
	<div>
		<h1 class="page-title">CI Runs</h1>
		<p class="page-subtitle">{data.total} pipeline execution{data.total !== 1 ? 's' : ''}</p>
	</div>

	<!-- Filter bar -->
	<div class="filter-bar">
		<Filter class="w-4 h-4" style="color: var(--text-tertiary)" />

		<select
			class="filter-select"
			value={data.pipeline || ''}
			onchange={(e) => applyFilter('pipeline', (e.target as HTMLSelectElement).value)}
		>
			<option value="">All pipelines</option>
			<option value="nightly">Nightly</option>
			<option value="weekly">Weekly</option>
			<option value="pr">PR</option>
			<option value="main">Main</option>
			<option value="release">Release</option>
		</select>

		<select
			class="filter-select"
			value={data.verdict || ''}
			onchange={(e) => applyFilter('verdict', (e.target as HTMLSelectElement).value)}
		>
			<option value="">All verdicts</option>
			<option value="pass">Pass</option>
			<option value="fail">Fail</option>
		</select>

		{#if data.pipeline || data.verdict}
			<button
				class="filter-select"
				style="color: var(--accent); border-color: var(--accent)"
				onclick={() => goto('/runs', { replaceState: true, invalidateAll: true })}
			>
				Clear filters
			</button>
		{/if}
	</div>

	<!-- Runs table -->
	<div class="card">
		<div class="overflow-x-auto">
			<table class="table">
				<thead>
					<tr>
						<th>Date</th>
						<th>Pipeline</th>
						<th>Branch</th>
						<th>Commit</th>
						<th>Verdict</th>
						<th>Severity</th>
						<th>Issues</th>
						<th>Cost</th>
						<th>Duration</th>
					</tr>
				</thead>
				<tbody>
					{#each data.runs as run}
						<tr class="cursor-pointer" onclick={() => goto(`/runs/${run.id}`)}>
							<td style="font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap">{formatDate(run.created_at)}</td>
							<td><span class="badge badge-neutral">{run.pipeline}</span></td>
							<td style="font-family: var(--font-mono); font-size: 0.75rem">{run.branch}</td>
							<td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-tertiary)">{run.commit_sha}</td>
							<td>
								{#if run.verdict === 'pass'}
									<span class="badge badge-success"><CheckCircle class="w-3 h-3" /> Pass</span>
								{:else}
									<span class="badge badge-error"><XCircle class="w-3 h-3" /> Fail</span>
								{/if}
							</td>
							<td>
								<span class="badge {run.severity === 'critical' ? 'badge-error' : run.severity === 'high' ? 'badge-warning' : 'badge-neutral'}">
									{run.severity}
								</span>
							</td>
							<td style="font-weight: 500; color: {run.total_issues > 10 ? 'var(--error)' : 'var(--text-primary)'}">{run.total_issues}</td>
							<td style="color: var(--text-secondary)">${run.total_cost.toFixed(2)}</td>
							<td style="font-size: 0.75rem; color: var(--text-secondary)"><Clock class="inline w-3 h-3" /> {formatDuration(run.duration_seconds)}</td>
						</tr>
					{:else}
						<tr>
							<td colspan="9" style="text-align: center; color: var(--text-tertiary); padding: 32px">No runs match your filters</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
