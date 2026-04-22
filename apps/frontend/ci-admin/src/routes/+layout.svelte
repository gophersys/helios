<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { Activity, BarChart3, FileWarning, Flame, Zap } from 'lucide-svelte';

	let { children } = $props();

	const nav = [
		{ href: '/', label: 'Overview', icon: Activity },
		{ href: '/runs', label: 'Runs', icon: Zap },
		{ href: '/trends', label: 'Trends', icon: BarChart3 },
		{ href: '/hotspots', label: 'Hotspots', icon: Flame },
	];

	function isActive(href: string, pathname: string) {
		if (href === '/') return pathname === '/';
		return pathname.startsWith(href);
	}
</script>

<div class="flex h-screen overflow-hidden">
	<!-- Sidebar -->
	<aside class="w-60 flex-shrink-0 bg-sidebar-bg border-r border-border flex flex-col">
		<!-- Brand -->
		<div class="h-16 flex items-center px-5 border-b border-border">
			<div class="flex items-center gap-2">
				<div class="w-7 h-7 rounded-md bg-accent flex items-center justify-center">
					<Zap class="w-4 h-4 text-white" />
				</div>
				<span class="font-semibold text-text-primary tracking-tight">Concord CI</span>
			</div>
		</div>

		<!-- Nav -->
		<nav class="flex-1 px-3 py-4 space-y-1">
			{#each nav as item}
				<a
					href={item.href}
					class="sidebar-link {isActive(item.href, $page.url.pathname) ? 'sidebar-link-active' : ''}"
				>
					<item.icon class="w-4 h-4" />
					{item.label}
				</a>
			{/each}
		</nav>

		<!-- Footer -->
		<div class="px-5 py-4 border-t border-border">
			<p class="text-2xs text-text-tertiary">concord-ci v0.1.0</p>
		</div>
	</aside>

	<!-- Main -->
	<main class="flex-1 overflow-y-auto">
		<div class="max-w-6xl mx-auto px-6 py-6">
			{@render children()}
		</div>
	</main>
</div>
