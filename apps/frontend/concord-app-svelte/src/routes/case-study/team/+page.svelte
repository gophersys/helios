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

  // Pre-AI data (before Dec 28, 2025)
  const preAiContributors: ContributorStats[] = [
    { name: 'Mateo', commits: 431, insertions: 146769, deletions: 98537, net: 48232, repos: 8, color: 'accent' },
    { name: 'Jared', commits: 34, insertions: 23002, deletions: 17452, net: 5550, repos: 2, color: 'error' },
    { name: 'Chris', commits: 3, insertions: 454, deletions: 135, net: 319, repos: 1, color: 'success' },
    { name: 'Christian', commits: 3, insertions: 454, deletions: 135, net: 319, repos: 1, color: 'warning' },
  ];

  // Full year data (Mar 2025 - Mar 2026, including AI period)
  const fullYearContributors: ContributorStats[] = [
    { name: 'Mateo', commits: 253, insertions: 312027, deletions: 152568, net: 159459, repos: 11, color: 'accent' },
    { name: 'Chris', commits: 280, insertions: 24616, deletions: 1843, net: 22773, repos: 8, color: 'success' },
    { name: 'Christian', commits: 138, insertions: 4258, deletions: 1512, net: 2746, repos: 4, color: 'warning' },
    { name: 'Jared', commits: 41, insertions: 23635, deletions: 17626, net: 6009, repos: 3, color: 'error' },
  ];

  // Per-repo breakdown with sizes (full year)
  const repos: RepoStats[] = [
    { name: 'concord', description: 'Main platform monorepo', contributors: [{ contributor: 'Mateo', commits: 211, net: 98175 }, { contributor: 'Jared', commits: 37, net: 5990 }] },
    { name: 'alpha_fw', description: 'Alpha product firmware', contributors: [{ contributor: 'Chris', commits: 179, net: 8212 }, { contributor: 'Christian', commits: 103, net: 1828 }, { contributor: 'Mateo', commits: 3, net: 31 }] },
    { name: 'vsm_drv', description: 'Vital signs monitor driver', contributors: [{ contributor: 'Mateo', commits: 2, net: 33363 }] },
    { name: 'lsm6dso_drv', description: 'Accelerometer/gyro driver', contributors: [{ contributor: 'Mateo', commits: 5, net: 17218 }] },
    { name: 'pah8151_drv', description: 'PPG sensor driver', contributors: [{ contributor: 'Mateo', commits: 12, net: 8881 }, { contributor: 'Chris', commits: 3, net: 62 }] },
    { name: 'sigma5_mfg_fw', description: 'Sigma5 manufacturing firmware', contributors: [{ contributor: 'Chris', commits: 23, net: 5834 }] },
    { name: 'ck_boards', description: 'Zephyr board definitions', contributors: [{ contributor: 'Chris', commits: 49, net: 918 }, { contributor: 'Christian', commits: 29, net: 918 }] },
  ];

  // All repository sizes (lines of code)
  interface RepoSize {
    name: string;
    lines: number;
    category: 'platform' | 'firmware' | 'driver' | 'library';
  }

  const repoSizes: RepoSize[] = [
    { name: 'concord', lines: 166115, category: 'platform' },
    { name: 'sigma5_fw', lines: 77996, category: 'firmware' },
    { name: 'vsm_drv', lines: 33342, category: 'driver' },
    { name: 'lsm6dso_drv', lines: 17215, category: 'driver' },
    { name: 'se050_drv', lines: 11442, category: 'driver' },
    { name: 'pah8151_drv', lines: 8939, category: 'driver' },
    { name: 'alpha_mfg_fw', lines: 8466, category: 'firmware' },
    { name: 'alpha_fw', lines: 8223, category: 'firmware' },
    { name: 'sigma5_mfg_fw', lines: 5827, category: 'firmware' },
    { name: 'accel_drv', lines: 5754, category: 'driver' },
    { name: 'cipher-posix', lines: 4599, category: 'library' },
    { name: 'dns_sec', lines: 4254, category: 'library' },
    { name: 'cipher', lines: 3949, category: 'library' },
    { name: 'iface', lines: 3895, category: 'library' },
    { name: 'iface-posix', lines: 2978, category: 'library' },
    { name: 'alt_drv', lines: 1871, category: 'driver' },
    { name: 'mlx90614_drv', lines: 1791, category: 'driver' },
    { name: 'ck_boards', lines: 1582, category: 'library' },
    { name: 'm24c08_drv', lines: 806, category: 'driver' },
    { name: 'dut_gpio_config_drv', lines: 490, category: 'driver' },
    { name: 'sn74lv051a_drv', lines: 229, category: 'driver' },
    { name: 'mcp4017_drv', lines: 180, category: 'driver' },
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
    ? 'Before Dec 28, 2025 (Pre-AI)'
    : 'Mar 2025 - Mar 2026 (Full Year)');

  function formatNumber(n: number): string {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
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
        Pre-AI (before Dec 28)
      </button>
      <button
        onclick={() => selectedPeriod = 'full-year'}
        class="px-4 py-2 text-sm font-medium rounded-md transition-colors {selectedPeriod === 'full-year' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-secondary'}"
      >
        Full Year
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
          <div class="text-xl font-semibold text-text-primary">+{formatNumber(totalNet)}</div>
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
          <div class="text-xl font-semibold text-text-primary">{selectedPeriod === 'pre-ai' ? 8 : 27}</div>
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
              <span class="text-sm font-semibold {getTextColorClass(contributor.color)}">
                +{formatNumber(contributor.net)}
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
                <td class="text-right py-3 font-semibold {getTextColorClass(c.color)}">
                  +{formatNumber(c.net)}
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
              <td class="text-right py-3 font-semibold text-accent">
                +{formatNumber(totalNet)}
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
      <h3 class="text-sm font-semibold text-text-primary">Codebase Size by Repository</h3>
      <div class="flex items-center gap-4 text-2xs">
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-accent"></div>
          <span class="text-text-tertiary">Platform</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-success"></div>
          <span class="text-text-tertiary">Firmware</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-warning"></div>
          <span class="text-text-tertiary">Driver</span>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="w-2 h-2 rounded-full bg-error"></div>
          <span class="text-text-tertiary">Library</span>
        </div>
      </div>
    </div>

    <!-- Treemap-style visualization -->
    <div class="grid grid-cols-12 gap-1 h-48">
      {#each repoSizes.slice(0, 12) as repo}
        {@const width = Math.max(1, Math.round((repo.lines / totalRepoLines) * 36))}
        <div
          class="col-span-{Math.min(width, 6)} rounded-lg {getCategoryColor(repo.category)} flex flex-col items-center justify-center p-2 text-center transition-all hover:opacity-80"
          title="{repo.name}: {formatNumber(repo.lines)} lines"
        >
          <span class="text-2xs font-medium text-surface-0 truncate w-full">{repo.name}</span>
          <span class="text-xs font-bold text-surface-0">{formatNumber(repo.lines)}</span>
        </div>
      {/each}
    </div>

    <!-- Bar chart for all repos -->
    <div class="mt-6 space-y-2">
      {#each repoSizes as repo}
        {@const percentage = (repo.lines / maxRepoSize) * 100}
        <div class="flex items-center gap-3">
          <span class="w-28 text-2xs text-text-secondary font-mono truncate">{repo.name}</span>
          <div class="flex-1 h-4 bg-surface-1 rounded overflow-hidden">
            <div
              class="h-full rounded transition-all {getCategoryColor(repo.category)}"
              style:width="{percentage}%"
            ></div>
          </div>
          <span class="w-14 text-right text-2xs text-text-tertiary">{formatNumber(repo.lines)}</span>
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
    <h3 class="text-lg font-semibold text-text-primary mb-4">AI Impact Analysis</h3>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <div class="text-center p-4 bg-surface-0 rounded-lg">
        <div class="text-2xs text-text-tertiary mb-1">Mateo Pre-AI</div>
        <div class="text-2xl font-bold text-text-secondary">+48K</div>
        <div class="text-2xs text-text-tertiary">431 commits</div>
      </div>
      <div class="text-center p-4 bg-surface-0 rounded-lg">
        <div class="text-2xs text-text-tertiary mb-1">Mateo Post-AI</div>
        <div class="text-2xl font-bold text-accent">+159K</div>
        <div class="text-2xs text-text-tertiary">253 commits (last year)</div>
      </div>
      <div class="text-center p-4 bg-surface-0 rounded-lg">
        <div class="text-2xs text-text-tertiary mb-1">Productivity Increase</div>
        <div class="text-2xl font-bold text-success">3.3x</div>
        <div class="text-2xs text-text-tertiary">net lines per commit</div>
      </div>
    </div>
    <p class="text-sm text-text-secondary mt-4 text-center">
      AI augmentation increased net output from ~112 lines/commit to ~630 lines/commit
    </p>
  </div>
</div>
