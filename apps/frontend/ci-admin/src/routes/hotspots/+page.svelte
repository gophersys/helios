<script lang="ts">
	import { Flame, FileCode, AlertTriangle } from 'lucide-svelte';

	let { data } = $props();
	const maxAppearances = Math.max(...data.hotspots.map((h: any) => h.appearances), 1);
</script>

<div class="space-y-6" style="animation: fade-in 0.2s ease-out;">
	<div>
		<h1 class="page-title">Hotspots</h1>
		<p class="page-subtitle">Files flagged most frequently by AI reviews</p>
	</div>

	<div class="card">
		<div class="overflow-x-auto">
			<table class="table">
				<thead>
					<tr>
						<th>File</th>
						<th>Appearances</th>
						<th>Stages</th>
						<th>Severities</th>
					</tr>
				</thead>
				<tbody>
					{#each data.hotspots as hotspot, i}
						<tr>
							<td>
								<div class="flex items-center gap-2">
									{#if i === 0}
										<Flame class="w-4 h-4 flex-shrink-0" style="color: var(--error)" />
									{:else if i < 3}
										<AlertTriangle class="w-4 h-4 flex-shrink-0" style="color: var(--warning)" />
									{:else}
										<FileCode class="w-4 h-4 flex-shrink-0" style="color: var(--text-tertiary)" />
									{/if}
									<code style="font-size: 0.75rem">{hotspot.file}</code>
								</div>
							</td>
							<td>
								<div class="flex items-center gap-2">
									<div style="width: 64px; height: 8px; background: var(--surface-2); border-radius: 9999px; overflow: hidden">
										<div
											style="height: 100%; border-radius: 9999px; width: {(hotspot.appearances / maxAppearances) * 100}%; background: {hotspot.appearances >= 4 ? 'var(--error)' : hotspot.appearances >= 3 ? 'var(--warning)' : 'var(--info)'}"
										></div>
									</div>
									<span style="font-size: 0.875rem; font-weight: 500">{hotspot.appearances}x</span>
								</div>
							</td>
							<td>
								<div class="flex flex-wrap gap-1">
									{#each hotspot.stages as stage}
										<span class="badge badge-neutral">{stage}</span>
									{/each}
								</div>
							</td>
							<td>
								<div class="flex flex-wrap gap-1">
									{#each hotspot.severities as sev}
										<span class="badge {sev === 'critical' ? 'badge-error' : sev === 'high' ? 'badge-warning' : sev === 'medium' ? 'badge-info' : 'badge-neutral'}">
											{sev}
										</span>
									{/each}
								</div>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="4" style="text-align: center; color: var(--text-tertiary); padding: 32px">No hotspots yet</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
