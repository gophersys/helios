<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    Users,
    GitCommit,
    TrendingUp,
    ArrowLeft,
    Code,
    FolderGit2,
    Calendar,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  const auth = getAuth();

  type Period = 'pre-ai' | 'full-year';
  let selectedPeriod = $state<Period>('full-year');

  interface ContributorStats {
    name: string;
    commits: number;
    insertions: number;
    deletions: number;
    net: number;
    repos: number;
    color: string;
  }

  interface RepoContrib {
    contributor: string;
    commits: number;
    net: number;
  }

  interface RepoStats {
    name: string;
    description: string;
    contributors: RepoContrib[];
  }

  // Pre-AI data (Mar 12, 2024 - Dec 28, 2025)
  const preAiContributors: ContributorStats[] = [
    { name: 'Mateo', commits: 266, insertions: 113728, deletions: 83712, net: 30016, repos: 9, color: 'accent' },
    { name: 'Chris', commits: 335, insertions: 14914, deletions: 2498, net: 12416, repos: 8, color: 'success' },
    { name: 'Jared', commits: 36, insertions: 26275, deletions: 20015, net: 6260, repos: 3, color: 'error' },
    { name: 'Christian', commits: 142, insertions: 4639, deletions: 1415, net: 3224, repos: 8, color: 'warning' },
  ];

  // Full 2 years (Mar 12, 2024 - Mar 12, 2026)
  const fullYearContributors: ContributorStats[] = [
    { name: 'Mateo', commits: 974, insertions: 889661, deletions: 445581, net: 444080, repos: 15, color: 'accent' },
    { name: 'Chris', commits: 506, insertions: 85073, deletions: 6977, net: 78096, repos: 11, color: 'success' },
    { name: 'Jared', commits: 77, insertions: 49910, deletions: 37641, net: 12269, repos: 5, color: 'error' },
    { name: 'Christian', commits: 200, insertions: 1412844, deletions: 1401167, net: 11677, repos: 9, color: 'warning' },
  ];

  // Per-repo breakdown with sizes (full year)
  const repos: RepoStats[] = [
    { name: 'concord', description: 'Platform monorepo (Flask, SvelteKit, K8s)', contributors: [{ contributor: 'Mateo', commits: 567, net: 236874 }, { contributor: 'Jared', commits: 71, net: 11540 }] },
    { name: 'vsm_drv', description: 'Vital signs monitor driver', contributors: [{ contributor: 'Mateo', commits: 2, net: 33363 }] },
    { name: 'lsm6dso_drv', description: 'Accelerometer/gyro driver', contributors: [{ contributor: 'Mateo', commits: 5, net: 17218 }] },
    { name: 'pah8151_drv', description: 'PPG sensor driver', contributors: [{ contributor: 'Mateo', commits: 14, net: 8888 }, { contributor: 'Chris', commits: 3, net: 62 }] },
    { name: 'alpha_mfg_fw', description: 'Alpha manufacturing firmware', contributors: [{ contributor: 'Christian', commits: 5, net: 7742 }, { contributor: 'Chris', commits: 10, net: 812 }] },
    { name: 'alpha_fw', description: 'Alpha product firmware', contributors: [{ contributor: 'Chris', commits: 76, net: 6384 }, { contributor: 'Christian', commits: 103, net: 1828 }, { contributor: 'Mateo', commits: 3, net: 31 }] },
    { name: 'sigma5_mfg_fw', description: 'Sigma5 manufacturing firmware', contributors: [{ contributor: 'Chris', commits: 23, net: 5834 }] },
    { name: 'mlx90614_drv', description: 'IR temperature sensor driver', contributors: [{ contributor: 'Mateo', commits: 6, net: 1791 }] },
    { name: 'ck_boards', description: 'Zephyr board definitions', contributors: [{ contributor: 'Christian', commits: 29, net: 918 }, { contributor: 'Chris', commits: 20, net: 0 }] },
  ];

  // All repository sizes with contributor breakdown
  interface RepoSize {
    name: string;
    lines: number;
    category: 'platform' | 'firmware' | 'driver' | 'library';
    contributors: { name: string; pct: number }[];
  }

  // Contributor colors (same as main stats)
  const contributorColors: Record<string, string> = {
    'Mateo': 'bg-accent',
    'Chris': 'bg-success',
    'Jared': 'bg-error',
    'Christian': 'bg-warning',
  };

  // Repo sizes with contributor percentages (CUSTOM CODE ONLY - excludes vendor SDKs)
  // Excluded: LoRaMac-node (57K), PAH8151 SDK (7.5K), LSM6DSO SDK (16K), protobuf generated (2.7K)
  const repoSizes: RepoSize[] = [
    // Platform
    { name: 'concord', lines: 167000, category: 'platform', contributors: [{ name: 'Mateo', pct: 95 }, { name: 'Jared', pct: 5 }] },
    // Firmware
    { name: 'sigma5_fw', lines: 77996, category: 'firmware', contributors: [{ name: 'Jared', pct: 100 }] },
    { name: 'se050_drv', lines: 11442, category: 'firmware', contributors: [{ name: 'Chris', pct: 100 }] },
    { name: 'alpha_mfg_fw', lines: 8466, category: 'firmware', contributors: [{ name: 'Christian', pct: 90 }, { name: 'Chris', pct: 10 }] },
    { name: 'alpha_fw', lines: 8223, category: 'firmware', contributors: [{ name: 'Chris', pct: 75 }, { name: 'Christian', pct: 22 }, { name: 'Mateo', pct: 3 }] },
    { name: 'comm_coproc_mfg', lines: 7839, category: 'firmware', contributors: [{ name: 'Chris', pct: 100 }] },
    { name: 'theta_fw', lines: 7955, category: 'firmware', contributors: [{ name: 'Chris', pct: 97 }, { name: 'Christian', pct: 3 }] },
    { name: 'theta_mfg_fw', lines: 7739, category: 'firmware', contributors: [{ name: 'Mateo', pct: 94 }, { name: 'Chris', pct: 6 }] },
    { name: 'sigma5_mfg_fw', lines: 5827, category: 'firmware', contributors: [{ name: 'Chris', pct: 100 }] },
    // Drivers (custom code only, vendor SDKs excluded)
    { name: 'vsm_drv', lines: 9944, category: 'driver', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'accel_drv', lines: 5754, category: 'driver', contributors: [{ name: 'Chris', pct: 100 }] },
    { name: 'alt_drv', lines: 1871, category: 'driver', contributors: [{ name: 'Chris', pct: 100 }] },
    { name: 'mlx90614_drv', lines: 1791, category: 'driver', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'lsm6dso_drv', lines: 1357, category: 'driver', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'pah8151_drv', lines: 1335, category: 'driver', contributors: [{ name: 'Mateo', pct: 99 }, { name: 'Chris', pct: 1 }] },
    { name: 'm24c08_drv', lines: 806, category: 'driver', contributors: [{ name: 'Christian', pct: 100 }] },
    { name: 'dut_gpio_config_drv', lines: 490, category: 'driver', contributors: [] },
    { name: 'sn74lv051a_drv', lines: 229, category: 'driver', contributors: [] },
    { name: 'mcp4017_drv', lines: 155, category: 'driver', contributors: [] },
    // Libraries
    { name: 'cipher-posix', lines: 4599, category: 'library', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'dns_sec', lines: 4254, category: 'library', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'cipher', lines: 3949, category: 'library', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'iface', lines: 3895, category: 'library', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'iface-posix', lines: 2978, category: 'library', contributors: [{ name: 'Mateo', pct: 100 }] },
    { name: 'ck_boards', lines: 1582, category: 'library', contributors: [{ name: 'Christian', pct: 55 }, { name: 'Chris', pct: 45 }] },
  ];

  const maxRepoSize = Math.max(...repoSizes.map(r => r.lines));
  const totalRepoLines = repoSizes.reduce((sum, r) => sum + r.lines, 0);

  function getCategoryColor(cat: string): string {
    return { platform: 'bg-accent', firmware: 'bg-success', driver: 'bg-warning', library: 'bg-error' }[cat] || 'bg-accent';
  }

  const contributors = $derived(selectedPeriod === 'pre-ai' ? preAiContributors : fullYearContributors);
  const totalNet = $derived(contributors.reduce((sum, c) => sum + c.net, 0));
  const totalCommits = $derived(contributors.reduce((sum, c) => sum + c.commits, 0));
  const maxNet = $derived(Math.max(...contributors.map(c => c.net)));

  const periodLabel = $derived(selectedPeriod === 'pre-ai'
    ? 'Mar 2024 - Dec 2025 (Pre-AI)'
    : 'Mar 2024 - Mar 2026 (Full 2 Years)');

  function formatNumber(n: number): string {
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (abs >= 1000000) return sign + (abs / 1000000).toFixed(1) + 'M';
    if (abs >= 1000) return sign + (abs / 1000).toFixed(0) + 'K';
    return n.toString();
  }

  function getColorClass(color: string): string {
    return { accent: 'bg-accent', success: 'bg-success', warning: 'bg-warning', error: 'bg-error' }[color] || 'bg-accent';
  }

  function getTextColorClass(color: string): string {
    return { accent: 'text-accent', success: 'text-success', warning: 'text-warning', error: 'text-error' }[color] || 'text-accent';
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
    }
  });
</script>

<svelte:head>
  <title>Team Comparison — Concord</title>
</svelte:head>

<div class="animate-fade-in space-y-6">
  <PageHeader
    title="Team Productivity"
    description={periodLabel}
  >
    {#snippet actions()}
      <a
        href="/case-study"
        class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-1"
      >
        <ArrowLeft size={16} />
        AI Case Study
      </a>
    {/snippet}
  </PageHeader>

  <!-- Period Selector -->
  <div class="flex items-center gap-2">
    <Calendar size={16} class="text-text-tertiary" />
    <div class="flex rounded-lg bg-surface-1 p-1">
      <button
        onclick={() => selectedPeriod = 'pre-ai'}
        class="px-4 py-2 text-sm font-medium rounded-md transition-colors {selectedPeriod === 'pre-ai' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-secondary'}"
      >
        Pre-AI (Mar 24 - Dec 25)
      </button>
      <button
        onclick={() => selectedPeriod = 'full-year'}
        class="px-4 py-2 text-sm font-medium rounded-md transition-colors {selectedPeriod === 'full-year' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-secondary'}"
      >
        Full 2 Years
      </button>
    </div>
  </div>

  <!-- Summary Cards -->
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
          <Users size={20} class="text-accent" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Contributors</div>
          <div class="text-xl font-semibold text-text-primary">{contributors.length}</div>
        </div>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-success/10">
          <TrendingUp size={20} class="text-success" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Total Net Lines</div>
          <div class="text-xl font-semibold {totalNet >= 0 ? 'text-text-primary' : 'text-error'}">{totalNet >= 0 ? '+' : ''}{formatNumber(totalNet)}</div>
        </div>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10">
          <GitCommit size={20} class="text-warning" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Total Commits</div>
          <div class="text-xl font-semibold text-text-primary">{totalCommits}</div>
        </div>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-error/10">
          <FolderGit2 size={20} class="text-error" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Repositories</div>
          <div class="text-xl font-semibold text-text-primary">{selectedPeriod === 'pre-ai' ? 11 : 18}</div>
        </div>
      </div>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Contributor Comparison -->
    <div class="card p-5">
      <h3 class="text-sm font-semibold text-text-primary mb-4">Net Lines by Contributor</h3>
      <div class="space-y-4">
        {#each contributors as contributor}
          {@const percentage = (contributor.net / maxNet) * 100}
          <div>
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <div class="w-3 h-3 rounded-full {getColorClass(contributor.color)}"></div>
                <span class="text-sm font-medium text-text-primary">{contributor.name}</span>
              </div>
              <span class="text-sm font-semibold {contributor.net >= 0 ? getTextColorClass(contributor.color) : 'text-error'}">
                {contributor.net >= 0 ? '+' : ''}{formatNumber(contributor.net)}
              </span>
            </div>
            <div class="h-4 bg-surface-1 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all {getColorClass(contributor.color)}"
                style:width="{percentage}%"
              ></div>
            </div>
            <div class="flex justify-between mt-1 text-2xs text-text-tertiary">
              <span>{contributor.commits} commits</span>
              <span>{contributor.repos} repos</span>
            </div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Detailed Stats Table -->
    <div class="card p-5">
      <h3 class="text-sm font-semibold text-text-primary mb-4">Detailed Statistics</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left py-2 text-text-tertiary font-medium">Contributor</th>
              <th class="text-right py-2 text-text-tertiary font-medium">Commits</th>
              <th class="text-right py-2 text-text-tertiary font-medium">Inserted</th>
              <th class="text-right py-2 text-text-tertiary font-medium">Deleted</th>
              <th class="text-right py-2 text-text-tertiary font-medium">Net</th>
            </tr>
          </thead>
          <tbody>
            {#each contributors as c}
              <tr class="border-b border-border/50">
                <td class="py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full {getColorClass(c.color)}"></div>
                    <span class="font-medium text-text-primary">{c.name}</span>
                  </div>
                </td>
                <td class="text-right py-3 text-text-secondary">{c.commits}</td>
                <td class="text-right py-3 text-success">+{formatNumber(c.insertions)}</td>
                <td class="text-right py-3 text-error">-{formatNumber(c.deletions)}</td>
                <td class="text-right py-3 font-semibold {c.net >= 0 ? getTextColorClass(c.color) : 'text-error'}">
                  {c.net >= 0 ? '+' : ''}{formatNumber(c.net)}
                </td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            <tr class="border-t-2 border-border">
              <td class="py-3 font-semibold text-text-primary">Total</td>
              <td class="text-right py-3 font-semibold text-text-primary">{totalCommits}</td>
              <td class="text-right py-3 font-semibold text-success">
                +{formatNumber(contributors.reduce((s, c) => s + c.insertions, 0))}
              </td>
              <td class="text-right py-3 font-semibold text-error">
                -{formatNumber(contributors.reduce((s, c) => s + c.deletions, 0))}
              </td>
              <td class="text-right py-3 font-semibold {totalNet >= 0 ? 'text-accent' : 'text-error'}">
                {totalNet >= 0 ? '+' : ''}{formatNumber(totalNet)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  </div>

  <!-- Repository Breakdown (Full Year Only) -->
  {#if selectedPeriod === 'full-year'}
    <div class="card p-5">
      <h3 class="text-sm font-semibold text-text-primary mb-4">Repository Breakdown</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left py-3 text-text-tertiary font-medium">Repository</th>
              <th class="text-left py-3 text-text-tertiary font-medium">Description</th>
              <th class="text-left py-3 text-text-tertiary font-medium">Contributors</th>
              <th class="text-right py-3 text-text-tertiary font-medium">Net Lines</th>
            </tr>
          </thead>
          <tbody>
            {#each repos as repo}
              {@const repoTotal = repo.contributors.reduce((s, c) => s + c.net, 0)}
              <tr class="border-b border-border/50 hover:bg-surface-1/50">
                <td class="py-3">
                  <div class="flex items-center gap-2">
                    <Code size={14} class="text-text-tertiary" />
                    <span class="font-medium text-text-primary font-mono">{repo.name}</span>
                  </div>
                </td>
                <td class="py-3 text-text-secondary text-2xs">{repo.description}</td>
                <td class="py-3">
                  <div class="flex flex-wrap gap-2">
                    {#each repo.contributors as contrib}
                      {@const c = fullYearContributors.find(x => x.name === contrib.contributor)}
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-1 text-2xs">
                        <span class="w-1.5 h-1.5 rounded-full {getColorClass(c?.color || 'accent')}"></span>
                        <span class="text-text-secondary">{contrib.contributor}</span>
                        <span class="text-text-tertiary">({contrib.commits})</span>
                      </span>
                    {/each}
                  </div>
                </td>
                <td class="py-3 text-right">
                  <span class="font-semibold text-success">+{formatNumber(repoTotal)}</span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}

  <!-- Repository Sizes Visualization -->
  <div class="card p-5">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-sm font-semibold text-text-primary">Original Code by Repository</h3>
        <p class="text-2xs text-text-tertiary mt-0.5">Excludes vendor SDKs (LoRaMac, PAH8151, LSM6DSO) and generated code</p>
      </div>
      <div class="flex items-center gap-4 text-2xs">
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-accent"></div>
          <span class="text-text-tertiary">Mateo</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-success"></div>
          <span class="text-text-tertiary">Chris</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-error"></div>
          <span class="text-text-tertiary">Jared</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-warning"></div>
          <span class="text-text-tertiary">Christian</span>
        </div>
      </div>
    </div>

    <!-- Grouped by category -->
    <div class="space-y-4">
      {#each ['platform', 'firmware', 'driver', 'library'] as category}
        {@const categoryRepos = repoSizes.filter(r => r.category === category)}
        {@const categoryTotal = categoryRepos.reduce((s, r) => s + r.lines, 0)}
        <div class="p-3 bg-surface-1 rounded-lg">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-semibold text-text-primary capitalize">{category}</span>
            <span class="text-2xs text-text-tertiary">{formatNumber(categoryTotal)} lines</span>
          </div>
          <div class="space-y-1.5">
            {#each categoryRepos as repo}
              {@const barWidth = (repo.lines / maxRepoSize) * 100}
              <div class="flex items-center gap-2">
                <span class="w-24 text-2xs text-text-secondary font-mono truncate">{repo.name}</span>
                <div class="flex-1 h-5 bg-surface-2 rounded overflow-hidden flex">
                  {#each repo.contributors as contrib}
                    <div
                      class="{contributorColors[contrib.name]} h-full transition-all"
                      style:width="{(barWidth * contrib.pct) / 100}%"
                      title="{contrib.name}: {contrib.pct}%"
                    ></div>
                  {/each}
                  {#if repo.contributors.length === 0}
                    <div class="bg-surface-2 h-full" style:width="{barWidth}%"></div>
                  {/if}
                </div>
                <span class="w-12 text-right text-2xs text-text-tertiary">{formatNumber(repo.lines)}</span>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>

    <div class="mt-4 pt-4 border-t border-border flex items-center justify-between text-sm">
      <span class="text-text-secondary">Total across {repoSizes.length} repositories</span>
      <span class="font-semibold text-text-primary">{formatNumber(totalRepoLines)} lines</span>
    </div>
  </div>

  <!-- AI Impact Comparison -->
  <div class="card p-6 bg-accent/5 border-accent/20">
    <h3 class="text-lg font-semibold text-text-primary mb-4">AI Impact Analysis (Mateo)</h3>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <div class="text-center p-4 bg-surface-0 rounded-lg">
        <div class="text-2xs text-text-tertiary mb-1">Pre-AI (Mar 24 - Dec 25)</div>
        <div class="text-2xl font-bold text-text-secondary">+30K</div>
        <div class="text-2xs text-text-tertiary">266 commits (21 months)</div>
      </div>
      <div class="text-center p-4 bg-surface-0 rounded-lg">
        <div class="text-2xs text-text-tertiary mb-1">Post-AI (Dec 25 - Mar 26)</div>
        <div class="text-2xl font-bold text-accent">+414K</div>
        <div class="text-2xs text-text-tertiary">708 commits (10.5 weeks)</div>
      </div>
      <div class="text-center p-4 bg-surface-0 rounded-lg">
        <div class="text-2xs text-text-tertiary mb-1">Productivity Increase</div>
        <div class="text-2xl font-bold text-success">5.2x</div>
        <div class="text-2xs text-text-tertiary">lines/commit (113 → 585)</div>
      </div>
    </div>
    <p class="text-sm text-text-secondary mt-4 text-center">
      21 months pre-AI: +30K lines. 10.5 weeks post-AI: +414K lines. <strong class="text-accent">13.8x more output in 1/8th the time.</strong>
    </p>
  </div>
</div>
