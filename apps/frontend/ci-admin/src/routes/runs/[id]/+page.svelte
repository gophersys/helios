<script lang="ts">
	import { CheckCircle, XCircle, ArrowLeft, Clock, DollarSign, GitBranch, Hash, ChevronDown, ChevronRight, Terminal, AlertTriangle, FileCode } from 'lucide-svelte';
	import { stageClass, stageName } from '$lib/stage-colors';

	let { data } = $props();
	const { run } = data;

	// Track which stages are expanded
	let expandedStages = $state<Set<string>>(new Set());

	function toggleStage(stageId: string) {
		const next = new Set(expandedStages);
		if (next.has(stageId)) {
			next.delete(stageId);
		} else {
			next.add(stageId);
		}
		expandedStages = next;
	}

	function expandAll() {
		expandedStages = new Set(run.stages.map((s: any) => s.id));
	}
	function collapseAll() {
		expandedStages = new Set();
	}

	function formatDuration(s: number): string {
		if (s === 0) return '—';
		return `${Math.floor(s / 60)}m ${s % 60}s`;
	}
	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
	}

	/** Colorize CI log output lines. */
	function colorizeLog(raw: string): string {
		if (!raw) return '<span class="log-dim">No logs captured for this stage.</span>';
		return raw
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/^(ok\s.*)$/gm, '<span class="log-ok">$1</span>')
			.replace(/^(err\s.*)$/gm, '<span class="log-err">$1</span>')
			.replace(/^(warn\s.*)$/gm, '<span class="log-warn">$1</span>')
			.replace(/^(info\s.*)$/gm, '<span class="log-info">$1</span>')
			.replace(/^(skip\s.*)$/gm, '<span class="log-skip">$1</span>')
			.replace(/^(──.+──)$/gm, '<span class="log-info">$1</span>')
			.replace(/^(\s+done in .+)$/gm, '<span class="log-dim">$1</span>')
			.replace(/^(BLOCKED:.*)$/gm, '<span class="log-err">$1</span>')
			.replace(/^(PASS:.*)$/gm, '<span class="log-ok">$1</span>')
			.replace(/^(FAIL:.*)$/gm, '<span class="log-err">$1</span>');
	}

	// Group findings by stage
	function findingsForStage(stageName: string) {
		return run.findings.filter((f: any) => f.stage === stageName);
	}
</script>

<div class="space-y-5" style="animation: fade-in 0.2s ease-out;">
	<!-- Header -->
	<div>
		<a href="/runs" class="inline-flex items-center gap-1 text-sm mb-3" style="color: var(--text-secondary)">
			<ArrowLeft class="w-4 h-4" /> Back to runs
		</a>
		<div class="flex items-center gap-3">
			{#if run.verdict === 'pass'}
				<CheckCircle class="w-6 h-6" style="color: var(--success)" />
			{:else}
				<XCircle class="w-6 h-6" style="color: var(--error)" />
			{/if}
			<h1 class="page-title">{run.pipeline} &mdash; {run.verdict}</h1>
		</div>
		<div class="flex items-center gap-4 mt-2 text-sm flex-wrap" style="color: var(--text-secondary)">
			<span><Clock class="inline w-3.5 h-3.5" /> {formatDate(run.created_at)}</span>
			<span><GitBranch class="inline w-3.5 h-3.5" /> {run.branch}</span>
			<span><Hash class="inline w-3.5 h-3.5" /> {run.commit_sha}</span>
			<span><DollarSign class="inline w-3.5 h-3.5" /> ${run.total_cost.toFixed(4)}</span>
			<span><Clock class="inline w-3.5 h-3.5" /> {formatDuration(run.duration_seconds)}</span>
			<span>{run.total_issues} issue{run.total_issues !== 1 ? 's' : ''}</span>
		</div>
	</div>

	<!-- Stage cards (GitHub Actions style) -->
	<div>
		<div class="flex items-center justify-between mb-3">
			<h2 style="font-size: 0.875rem; font-weight: 600">Stages ({run.stages.length})</h2>
			<div class="flex gap-2">
				<button
					class="text-xs font-medium px-2 py-1 rounded"
					style="color: var(--accent)"
					onclick={expandAll}
				>Expand all</button>
				<button
					class="text-xs font-medium px-2 py-1 rounded"
					style="color: var(--text-tertiary)"
					onclick={collapseAll}
				>Collapse all</button>
			</div>
		</div>

		<div class="space-y-2">
			{#each run.stages as stage}
				{@const isExpanded = expandedStages.has(stage.id)}
				{@const colorClass = stageClass(stage.name)}
				{@const findings = findingsForStage(stage.name)}

				<div class="collapse-card {colorClass}">
					<!-- Stage header -->
					<div
						class="collapse-header"
						onclick={() => toggleStage(stage.id)}
						role="button"
						tabindex="0"
					>
						<!-- Expand icon -->
						{#if isExpanded}
							<ChevronDown class="w-4 h-4" style="color: var(--text-tertiary)" />
						{:else}
							<ChevronRight class="w-4 h-4" style="color: var(--text-tertiary)" />
						{/if}

						<!-- Color indicator -->
						<div class="stage-dot"></div>

						<!-- Verdict icon -->
						{#if stage.verdict === 'pass'}
							<CheckCircle class="w-4 h-4" style="color: var(--success)" />
						{:else}
							<XCircle class="w-4 h-4" style="color: var(--error)" />
						{/if}

						<!-- Stage name -->
						<span style="font-weight: 500; font-size: 0.875rem; flex: 1">{stageName(stage.name)}</span>

						<!-- Meta badges -->
						<span class="badge {stage.severity === 'critical' ? 'badge-error' : stage.severity === 'high' ? 'badge-warning' : stage.severity === 'medium' ? 'badge-info' : 'badge-neutral'}">
							{stage.severity}
						</span>
						{#if stage.issues > 0}
							<span style="font-size: 0.75rem; font-weight: 500; color: var(--text-secondary)">{stage.issues} issue{stage.issues !== 1 ? 's' : ''}</span>
						{/if}
						<span style="font-size: 0.75rem; color: var(--text-tertiary)">${stage.cost.toFixed(3)}</span>
						{#if stage.duration_seconds > 0}
							<span style="font-size: 0.75rem; color: var(--text-tertiary)">{formatDuration(stage.duration_seconds)}</span>
						{/if}
					</div>

					<!-- Expanded content -->
					{#if isExpanded}
						<div class="collapse-body">
							<!-- Summary -->
							{#if stage.summary}
								<div style="padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); font-size: 0.875rem; color: var(--text-secondary)">
									{stage.summary}
								</div>
							{/if}

							<!-- Findings -->
							{#if findings.length > 0}
								<div style="padding: 12px 16px; border-bottom: 1px solid var(--border-subtle)">
									<div style="font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px">
										<AlertTriangle class="inline w-3 h-3" /> Findings ({findings.length})
									</div>
									<div class="space-y-2">
										{#each findings as finding}
											<div style="padding: 8px 12px; background: var(--stage-bg); border-radius: 8px">
												<div class="flex items-center gap-2 mb-1">
													<span class="badge {finding.severity === 'critical' ? 'badge-error' : finding.severity === 'high' ? 'badge-warning' : finding.severity === 'medium' ? 'badge-info' : 'badge-neutral'}" style="font-size: 0.6875rem">
														{finding.severity}
													</span>
													{#if finding.file}
														<code style="font-size: 0.75rem; color: var(--stage-color)">
															<FileCode class="inline w-3 h-3" /> {finding.file}
														</code>
													{/if}
												</div>
												<p style="font-size: 0.8125rem; color: var(--text-secondary); margin-top: 2px">{finding.message}</p>
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Logs -->
							<div>
								<div style="padding: 8px 16px; font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px">
									<Terminal class="w-3 h-3" /> Logs
								</div>
								<div class="log-viewer">
									{@html colorizeLog(stage.logs)}
								</div>
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>
