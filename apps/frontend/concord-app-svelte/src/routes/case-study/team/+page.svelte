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
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  const auth = getAuth();

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
    contributors: RepoContrib[];
  }

  // Team data from analysis (past year: Mar 2025 - Mar 2026)
  const contributors: ContributorStats[] = [
    { name: 'Mateo', commits: 253, insertions: 312027, deletions: 152568, net: 159459, repos: 11, color: 'accent' },
    { name: 'Chris', commits: 280, insertions: 24616, deletions: 1843, net: 22773, repos: 8, color: 'success' },
    { name: 'Christian', commits: 138, insertions: 4258, deletions: 1512, net: 2746, repos: 4, color: 'warning' },
    { name: 'Jared', commits: 41, insertions: 23635, deletions: 17626, net: 6009, repos: 3, color: 'error' },
  ];

  // Per-repo breakdown (top repos)
  const repos: RepoStats[] = [
    {
      name: 'concord',
      contributors: [
        { contributor: 'Mateo', commits: 211, net: 98175 },
        { contributor: 'Jared', commits: 37, net: 5990 },
      ]
    },
    {
      name: 'alpha_fw',
      contributors: [
        { contributor: 'Chris', commits: 179, net: 8212 },
        { contributor: 'Christian', commits: 103, net: 1828 },
        { contributor: 'Mateo', commits: 3, net: 31 },
      ]
    },
    {
      name: 'vsm_drv',
      contributors: [
        { contributor: 'Mateo', commits: 2, net: 33363 },
      ]
    },
    {
      name: 'lsm6dso_drv',
      contributors: [
        { contributor: 'Mateo', commits: 5, net: 17218 },
      ]
    },
    {
      name: 'pah8151_drv',
      contributors: [
        { contributor: 'Mateo', commits: 12, net: 8881 },
        { contributor: 'Chris', commits: 3, net: 62 },
      ]
    },
    {
      name: 'sigma5_mfg_fw',
      contributors: [
        { contributor: 'Chris', commits: 23, net: 5834 },
      ]
    },
    {
      name: 'ck_boards',
      contributors: [
        { contributor: 'Chris', commits: 49, net: 918 },
        { contributor: 'Christian', commits: 29, net: 918 },
      ]
    },
  ];

  const totalNet = contributors.reduce((sum, c) => sum + c.net, 0);
  const totalCommits = contributors.reduce((sum, c) => sum + c.commits, 0);
  const maxNet = Math.max(...contributors.map(c => c.net));

  function formatNumber(n: number): string {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
    return n.toString();
  }

  function getColorClass(color: string): string {
    const map: Record<string, string> = {
      accent: 'bg-accent',
      success: 'bg-success',
      warning: 'bg-warning',
      error: 'bg-error',
    };
    return map[color] || 'bg-accent';
  }

  function getTextColorClass(color: string): string {
    const map: Record<string, string> = {
      accent: 'text-accent',
      success: 'text-success',
      warning: 'text-warning',
      error: 'text-error',
    };
    return map[color] || 'text-accent';
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
    title="Team Productivity Comparison"
    description="All repositories analysis: March 2025 - March 2026"
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
          <div class="text-xl font-semibold text-text-primary">27</div>
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

  <!-- Per-Repository Breakdown -->
  <div class="card p-5">
    <h3 class="text-sm font-semibold text-text-primary mb-4">Repository Breakdown</h3>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each repos as repo}
        <div class="p-4 bg-surface-1 rounded-lg">
          <div class="flex items-center gap-2 mb-3">
            <Code size={16} class="text-text-tertiary" />
            <span class="font-medium text-text-primary">{repo.name}</span>
          </div>
          <div class="space-y-2">
            {#each repo.contributors as contrib}
              {@const contributor = contributors.find(c => c.name === contrib.contributor)}
              <div class="flex items-center justify-between text-sm">
                <div class="flex items-center gap-2">
                  <div class="w-2 h-2 rounded-full {getColorClass(contributor?.color || 'accent')}"></div>
                  <span class="text-text-secondary">{contrib.contributor}</span>
                </div>
                <div class="text-right">
                  <span class="text-success font-medium">+{formatNumber(contrib.net)}</span>
                  <span class="text-text-tertiary text-2xs ml-1">({contrib.commits})</span>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- AI Impact Highlight -->
  <div class="card p-6 bg-accent/5 border-accent/20">
    <div class="flex flex-col sm:flex-row items-center justify-between gap-4">
      <div>
        <h3 class="text-lg font-semibold text-text-primary mb-1">AI-Augmented Impact</h3>
        <p class="text-sm text-text-secondary">
          Mateo's AI-augmented output represents <strong class="text-accent">{Math.round((159459 / totalNet) * 100)}%</strong> of total team net lines
        </p>
      </div>
      <div class="flex items-center gap-4">
        <div class="text-center">
          <div class="text-2xs text-text-tertiary">Without AI</div>
          <div class="text-lg font-semibold text-text-secondary">~{formatNumber(totalNet - 159459 + 2000)}</div>
        </div>
        <div class="text-center">
          <div class="text-2xs text-text-tertiary">With AI</div>
          <div class="text-lg font-semibold text-accent">{formatNumber(totalNet)}</div>
        </div>
      </div>
    </div>
  </div>
</div>
