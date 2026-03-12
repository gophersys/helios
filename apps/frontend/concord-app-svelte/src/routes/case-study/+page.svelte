<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    TrendingUp,
    GitCommit,
    FileCode,
    Calendar,
    ChevronRight,
    Users,
    DollarSign,
    Zap,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  const auth = getAuth();

  interface JournalEntry {
    date: string;
    file: string;
    summary: string;
    inserted: number;
    deleted: number;
    commits: number;
  }

  // Journal data - parsed from markdown files
  const journals: JournalEntry[] = [
    { date: '02.03.26', file: '020326', summary: 'Backend + frontend stack, permission system, hardware catalog', inserted: 22815, deleted: 1000, commits: 3 },
    { date: '02.04.26', file: '020426', summary: 'Codebases module, API standardization, OpenAPI docs', inserted: 4289, deleted: 500, commits: 2 },
    { date: '02.05.26', file: '020526', summary: 'Products module, System Monitor, infra v2, testing harness', inserted: 18389, deleted: 1000, commits: 4 },
    { date: '02.06.26', file: '020626', summary: 'MTIB server/client refactor, handler tests', inserted: 6380, deleted: 500, commits: 2 },
    { date: '02.09.26', file: '020926', summary: 'MTIB observability, live UART streaming, edge server', inserted: 20982, deleted: 1000, commits: 5 },
    { date: '02.10.26', file: '021026', summary: 'Catalog data model, Kubernetes routes, security hardening', inserted: 3368, deleted: 1000, commits: 3 },
    { date: '02.15.26', file: '021526', summary: 'IWSCK A0 bring-up firmware (BLE, fuel gauge, RS-232)', inserted: 1236, deleted: 500, commits: 2 },
    { date: '02.24.26', file: '022426', summary: 'ICLE firmware, analyzer integration, devcontainer overhaul', inserted: 38828, deleted: 3000, commits: 6 },
    { date: '03.02.26', file: '030226', summary: 'Major validation framework release, Stage 4 tests', inserted: 102640, deleted: 5000, commits: 8 },
    { date: '03.10.26', file: '031026', summary: 'Stage 4 FUOTA, CI pipeline, UART fix, SvelteKit migration', inserted: 105714, deleted: 3745, commits: 13 },
    { date: '03.11.26', file: '031126', summary: 'HTTP API overhaul, FUOTA test framework, queue auto-trigger', inserted: 29970, deleted: 6858, commits: 7 },
  ];

  // Totals
  const totalInserted = 436910;
  const totalDeleted = 40496;
  const totalNet = totalInserted - totalDeleted;
  const totalCommits = 92;
  const durationDays = 38;
  const durationWeeks = 5.5;

  // Phoenix engineer baseline ($120K base, 15% bonus, no benefits)
  const annualComp = 138000;
  const weeklyComp = Math.round(annualComp / 52);
  const periodCost = Math.round(weeklyComp * durationWeeks);

  // Productivity benchmarks (Phoenix area - slightly lower than coastal)
  const lowRate = 50;      // lines/day
  const avgRate = 75;      // Phoenix average
  const highRate = 100;    // High performer

  // Working days in period
  const workingDays = Math.round(durationWeeks * 5);

  // Expected output at each rate
  const lowExpected = lowRate * workingDays;
  const avgExpected = avgRate * workingDays;
  const highExpected = highRate * workingDays;

  // Multipliers
  const lowMultiplier = Math.round(totalNet / lowExpected);
  const avgMultiplier = Math.round(totalNet / avgExpected);
  const highMultiplier = Math.round(totalNet / highExpected);

  // Team equivalents
  const teamLow = Math.round(totalNet / lowExpected);
  const teamAvg = Math.round(totalNet / avgExpected);
  const teamHigh = Math.round(totalNet / highExpected);

  // Team costs
  const teamCostLow = teamLow * periodCost;
  const teamCostAvg = teamAvg * periodCost;
  const teamCostHigh = teamHigh * periodCost;

  // Selected journal for detail view
  let selectedJournal = $state<JournalEntry | null>(null);

  // Cumulative data for chart
  const cumulativeData = journals.reduce((acc, journal, i) => {
    const prevNet = i > 0 ? acc[i - 1].net : 0;
    const prevInserted = i > 0 ? acc[i - 1].totalInserted : 0;
    const prevDeleted = i > 0 ? acc[i - 1].totalDeleted : 0;
    acc.push({
      date: journal.date,
      net: prevNet + (journal.inserted - journal.deleted),
      totalInserted: prevInserted + journal.inserted,
      totalDeleted: prevDeleted + journal.deleted,
    });
    return acc;
  }, [] as { date: string; net: number; totalInserted: number; totalDeleted: number }[]);

  const maxNet = Math.max(...cumulativeData.map((d) => d.net));

  function formatNumber(n: number): string {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
    return n.toString();
  }

  function formatCurrency(n: number): string {
    if (n >= 1000000) return '$' + (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return '$' + (n / 1000).toFixed(0) + 'K';
    return '$' + n.toString();
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
    }
  });
</script>

<svelte:head>
  <title>Case Study — Concord</title>
</svelte:head>

<div class="animate-fade-in space-y-6">
  <PageHeader
    title="AI-Augmented Development"
    description="Productivity economics analysis: Feb 3 - Mar 12, 2026"
  />

  <!-- Summary Cards -->
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-success/10">
          <TrendingUp size={20} class="text-success" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Net Lines</div>
          <div class="text-xl font-semibold text-text-primary">+{formatNumber(totalNet)}</div>
        </div>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
          <GitCommit size={20} class="text-accent" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Commits</div>
          <div class="text-xl font-semibold text-text-primary">{totalCommits}</div>
        </div>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10">
          <Calendar size={20} class="text-warning" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Duration</div>
          <div class="text-xl font-semibold text-text-primary">{durationWeeks} weeks</div>
        </div>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-error/10">
          <Zap size={20} class="text-error" />
        </div>
        <div>
          <div class="text-2xs font-medium text-text-tertiary">Multiplier</div>
          <div class="text-xl font-semibold text-text-primary">{avgMultiplier}x</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Main content grid -->
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Left column: Charts -->
    <div class="lg:col-span-2 space-y-6">
      <!-- Cumulative Output Chart -->
      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Cumulative Output</h3>
        <div class="h-64 relative">
          <!-- Y-axis labels -->
          <div class="absolute left-0 top-0 h-full w-12 flex flex-col justify-between text-2xs text-text-tertiary">
            <span>{formatNumber(maxNet)}</span>
            <span>{formatNumber(maxNet * 0.75)}</span>
            <span>{formatNumber(maxNet * 0.5)}</span>
            <span>{formatNumber(maxNet * 0.25)}</span>
            <span>0</span>
          </div>
          <!-- Chart area -->
          <div class="absolute left-14 right-0 top-0 bottom-6 border-l border-b border-border">
            <svg class="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              <!-- Grid lines -->
              {#each [25, 50, 75] as y}
                <line x1="0" y1={y} x2="100" y2={y} stroke="currentColor" stroke-width="0.2" class="text-border" />
              {/each}
              <!-- Area fill -->
              <path
                d="M 0 100 {cumulativeData.map((d, i) => `L ${(i / (cumulativeData.length - 1)) * 100} ${100 - (d.net / maxNet) * 100}`).join(' ')} L 100 100 Z"
                fill="url(#gradient)"
                opacity="0.3"
              />
              <!-- Line -->
              <path
                d="M {cumulativeData.map((d, i) => `${(i / (cumulativeData.length - 1)) * 100} ${100 - (d.net / maxNet) * 100}`).join(' L ')}"
                fill="none"
                stroke="currentColor"
                stroke-width="0.5"
                class="text-accent"
              />
              <!-- Points -->
              {#each cumulativeData as d, i}
                <circle
                  cx={(i / (cumulativeData.length - 1)) * 100}
                  cy={100 - (d.net / maxNet) * 100}
                  r="1"
                  fill="currentColor"
                  class="text-accent"
                />
              {/each}
              <defs>
                <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="rgb(var(--color-accent))" />
                  <stop offset="100%" stop-color="rgb(var(--color-accent))" stop-opacity="0" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <!-- X-axis labels -->
          <div class="absolute left-14 right-0 bottom-0 h-6 flex justify-between text-2xs text-text-tertiary">
            <span>Feb 3</span>
            <span>Feb 15</span>
            <span>Mar 2</span>
            <span>Mar 12</span>
          </div>
        </div>
      </div>

      <!-- Daily Output Bar Chart -->
      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Output by Session</h3>
        <div class="space-y-2">
          {#each journals as journal}
            {@const netLines = journal.inserted - journal.deleted}
            {@const maxJournalNet = Math.max(...journals.map(j => j.inserted - j.deleted))}
            {@const barWidth = (netLines / maxJournalNet) * 100}
            <button
              onclick={() => selectedJournal = selectedJournal?.file === journal.file ? null : journal}
              class="w-full group"
            >
              <div class="flex items-center gap-3">
                <span class="w-16 text-2xs text-text-tertiary font-mono shrink-0">{journal.date}</span>
                <div class="flex-1 h-6 bg-surface-1 rounded overflow-hidden relative">
                  <!-- Inserted bar -->
                  <div
                    class="absolute inset-y-0 left-0 bg-success/20 transition-all group-hover:bg-success/30"
                    style:width="{(journal.inserted / maxJournalNet) * 100}%"
                  ></div>
                  <!-- Deleted overlay -->
                  <div
                    class="absolute inset-y-0 right-0 bg-error/20 transition-all group-hover:bg-error/30"
                    style:width="{(journal.deleted / maxJournalNet) * 100}%"
                  ></div>
                  <!-- Net line -->
                  <div
                    class="absolute top-1/2 -translate-y-1/2 h-1 bg-accent rounded transition-all"
                    style:width="{barWidth}%"
                  ></div>
                </div>
                <span class="w-16 text-right text-xs font-medium text-success shrink-0">
                  +{formatNumber(netLines)}
                </span>
              </div>
              {#if selectedJournal?.file === journal.file}
                <div class="mt-2 ml-19 p-3 bg-surface-1 rounded-lg text-left">
                  <p class="text-sm text-text-secondary mb-2">{journal.summary}</p>
                  <div class="flex gap-4 text-2xs">
                    <span class="text-success">+{formatNumber(journal.inserted)} inserted</span>
                    <span class="text-error">-{formatNumber(journal.deleted)} deleted</span>
                    <span class="text-text-tertiary">{journal.commits} commits</span>
                  </div>
                </div>
              {/if}
            </button>
          {/each}
        </div>
      </div>
    </div>

    <!-- Right column: Economics -->
    <div class="space-y-6">
      <!-- Baseline -->
      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Phoenix Engineer Baseline</h3>
        <div class="space-y-3">
          <div class="flex justify-between text-sm">
            <span class="text-text-secondary">Base Salary</span>
            <span class="text-text-primary font-medium">$120,000</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-text-secondary">Bonus (15%)</span>
            <span class="text-text-primary font-medium">$18,000</span>
          </div>
          <div class="border-t border-border pt-3 flex justify-between text-sm">
            <span class="text-text-primary font-medium">Total Comp</span>
            <span class="text-accent font-semibold">${formatNumber(annualComp)}/yr</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-text-secondary">{durationWeeks}-week cost</span>
            <span class="text-text-primary font-medium">{formatCurrency(periodCost)}</span>
          </div>
        </div>
      </div>

      <!-- Productivity Comparison -->
      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Productivity Benchmarks</h3>
        <div class="space-y-4">
          <div class="text-2xs text-text-tertiary mb-2">Lines/day (Phoenix area)</div>

          <div class="space-y-3">
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-text-secondary">Low ({lowRate}/day)</span>
                <span class="text-text-primary">{formatNumber(lowExpected)} lines</span>
              </div>
              <div class="h-2 bg-surface-1 rounded-full overflow-hidden">
                <div class="h-full bg-error/50 rounded-full" style:width="{(lowExpected / totalNet) * 100}%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-text-secondary">Average ({avgRate}/day)</span>
                <span class="text-text-primary">{formatNumber(avgExpected)} lines</span>
              </div>
              <div class="h-2 bg-surface-1 rounded-full overflow-hidden">
                <div class="h-full bg-warning/50 rounded-full" style:width="{(avgExpected / totalNet) * 100}%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-text-secondary">High ({highRate}/day)</span>
                <span class="text-text-primary">{formatNumber(highExpected)} lines</span>
              </div>
              <div class="h-2 bg-surface-1 rounded-full overflow-hidden">
                <div class="h-full bg-success/50 rounded-full" style:width="{(highExpected / totalNet) * 100}%"></div>
              </div>
            </div>
          </div>

          <div class="border-t border-border pt-3">
            <div class="flex justify-between text-sm mb-1">
              <span class="text-accent font-medium">Actual Output</span>
              <span class="text-accent font-semibold">{formatNumber(totalNet)} lines</span>
            </div>
            <div class="h-2 bg-surface-1 rounded-full overflow-hidden">
              <div class="h-full bg-accent rounded-full w-full"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Team Equivalent -->
      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Team Equivalent</h3>
        <div class="space-y-4">
          <div class="text-center py-4 bg-surface-1 rounded-lg">
            <div class="flex items-center justify-center gap-2 mb-2">
              <Users size={24} class="text-accent" />
            </div>
            <div class="text-3xl font-bold text-accent">{teamAvg}</div>
            <div class="text-sm text-text-secondary">engineers equivalent</div>
            <div class="text-2xs text-text-tertiary mt-1">at {avgRate} lines/day avg</div>
          </div>

          <div class="space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-text-secondary">Low rate ({lowRate}/day)</span>
              <span class="text-text-primary">{teamLow} engineers</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-text-secondary">High rate ({highRate}/day)</span>
              <span class="text-text-primary">{teamHigh} engineers</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Cost Comparison -->
      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Cost Comparison</h3>
        <div class="space-y-3">
          <div class="flex justify-between text-sm">
            <span class="text-text-secondary">Traditional team ({teamAvg} eng)</span>
            <span class="text-error font-medium">{formatCurrency(teamCostAvg)}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-text-secondary">Actual (1 eng + AI)</span>
            <span class="text-success font-medium">{formatCurrency(periodCost)}</span>
          </div>
          <div class="border-t border-border pt-3 flex justify-between text-sm">
            <span class="text-text-primary font-medium">Savings</span>
            <span class="text-success font-semibold">{formatCurrency(teamCostAvg - periodCost)}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-text-primary font-medium">ROI Multiplier</span>
            <span class="text-accent font-semibold">{Math.round(teamCostAvg / periodCost)}x</span>
          </div>
        </div>
      </div>

      <!-- Quality Note -->
      <div class="card p-5 bg-accent/5 border-accent/20">
        <h3 class="text-sm font-semibold text-text-primary mb-3">Quality Indicators</h3>
        <ul class="space-y-2 text-sm text-text-secondary">
          <li class="flex items-start gap-2">
            <FileCode size={14} class="text-accent mt-0.5 shrink-0" />
            <span>Production firmware (Zephyr RTOS)</span>
          </li>
          <li class="flex items-start gap-2">
            <FileCode size={14} class="text-accent mt-0.5 shrink-0" />
            <span>Full-stack features (Flask + SvelteKit)</span>
          </li>
          <li class="flex items-start gap-2">
            <FileCode size={14} class="text-accent mt-0.5 shrink-0" />
            <span>873 backend tests (was 434)</span>
          </li>
          <li class="flex items-start gap-2">
            <FileCode size={14} class="text-accent mt-0.5 shrink-0" />
            <span>K8s/Helm infrastructure</span>
          </li>
        </ul>
      </div>
    </div>
  </div>

  <!-- Bottom summary -->
  <div class="mt-8 card p-6 bg-surface-1">
    <div class="flex flex-col sm:flex-row items-center justify-between gap-4">
      <div class="text-center sm:text-left">
        <h3 class="text-lg font-semibold text-text-primary">Bottom Line</h3>
        <p class="text-sm text-text-secondary">
          {formatNumber(totalNet)} lines in {durationWeeks} weeks = <strong class="text-accent">{avgMultiplier}x</strong> typical productivity
        </p>
      </div>
      <div class="flex items-center gap-6">
        <div class="text-center">
          <div class="text-2xs text-text-tertiary">Traditional Cost</div>
          <div class="text-lg font-semibold text-error">{formatCurrency(teamCostAvg)}</div>
        </div>
        <ChevronRight size={20} class="text-text-tertiary" />
        <div class="text-center">
          <div class="text-2xs text-text-tertiary">Actual Cost</div>
          <div class="text-lg font-semibold text-success">{formatCurrency(periodCost)}</div>
        </div>
      </div>
    </div>
  </div>
</div>
