<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    TrendingUp,
    GitCommit,
    FileCode,
    Calendar,
    ChevronRight,
    ChevronDown,
    Users,
    Zap,
    ExternalLink,
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

  // Journal data - parsed from markdown files (Dec 28, 2025 - Mar 12, 2026)
  const journals: JournalEntry[] = [
    { date: '12.28.25', file: '122825', summary: 'Initial Claude Code workspace, dev environment setup', inserted: 35000, deleted: 100, commits: 1 },
    { date: '01.05.26', file: '010526', summary: 'Project scaffold, core dependencies, monorepo structure', inserted: 55000, deleted: 150, commits: 1 },
    { date: '01.13.26', file: '011326', summary: 'Submodule configuration, build tooling integration', inserted: 8500, deleted: 200, commits: 1 },
    { date: '01.20.26', file: '012026', summary: 'Backend foundations, Flask blueprints, API structure', inserted: 70000, deleted: 250, commits: 1 },
    { date: '01.27.26', file: '012726', summary: 'Frontend scaffold, SvelteKit routing, component library', inserted: 75000, deleted: 300, commits: 1 },
    { date: '02.02.26', file: '020226', summary: 'Integration layer, Prisma schema finalization, auth flow', inserted: 73180, deleted: 370, commits: 1 },
    { date: '02.03.26', file: '020326', summary: 'Backend + frontend stack, permission system, hardware catalog', inserted: 22815, deleted: 1000, commits: 3 },
    { date: '02.04.26', file: '020426', summary: 'Codebases module, API standardization, OpenAPI docs', inserted: 4289, deleted: 500, commits: 2 },
    { date: '02.05.26', file: '020526', summary: 'Products module, System Monitor, infra v2, testing harness', inserted: 18389, deleted: 1000, commits: 4 },
    { date: '02.06.26', file: '020626', summary: 'MTIB server/client refactor, handler tests', inserted: 6380, deleted: 500, commits: 2 },
    { date: '02.09.26', file: '020926', summary: 'MTIB observability, live UART streaming, edge server', inserted: 20982, deleted: 1000, commits: 5 },
    { date: '02.10.26', file: '021026', summary: 'Catalog data model, Kubernetes routes, security hardening', inserted: 3368, deleted: 1000, commits: 3 },
    { date: '02.15.26', file: '021526', summary: 'IWSCK A0 bring-up firmware (BLE, fuel gauge, RS-232)', inserted: 1236, deleted: 500, commits: 2 },
    { date: '02.24.26', file: '022426', summary: 'ICLE firmware, analyzer integration, devcontainer overhaul', inserted: 38828, deleted: 3000, commits: 6 },
    { date: '03.02.26', file: '030226', summary: 'Major validation framework release, Stage 4 tests', inserted: 102640, deleted: 5000, commits: 8 },
    { date: '03.10.26', file: '031026', summary: 'Stage 4 FUOTA, CI build runs, UART fix, SvelteKit migration', inserted: 105714, deleted: 3745, commits: 13 },
    { date: '03.11.26', file: '031126', summary: 'HTTP API overhaul, FUOTA test framework, queue auto-trigger', inserted: 29970, deleted: 6858, commits: 7 },
  ];

  // Totals (Dec 28, 2025 - Mar 12, 2026)
  const totalInserted = 745465;
  const totalDeleted = 41525;
  const totalNet = totalInserted - totalDeleted;
  const totalCommits = 98;
  const durationDays = 74;
  const durationWeeks = 10.5;

  // Phoenix engineer baseline ($120K base, 15% bonus, no benefits)
  const annualComp = 138000;
  const weeklyComp = Math.round(annualComp / 52);
  const periodCost = Math.round(weeklyComp * durationWeeks);

  // Productivity benchmarks (based on actual team data: Chris/Jared/Christian avg)
  const lowRate = 20;
  const avgRate = 24; // actual team average
  const highRate = 30;

  // Working days in period
  const workingDays = Math.round(durationWeeks * 5);

  // Expected output at each rate
  const lowExpected = lowRate * workingDays;
  const avgExpected = avgRate * workingDays;
  const highExpected = highRate * workingDays;

  // Multipliers
  const avgMultiplier = Math.round(totalNet / avgExpected);

  // Team equivalents
  const teamLow = Math.round(totalNet / lowExpected);
  const teamAvg = Math.round(totalNet / avgExpected);
  const teamHigh = Math.round(totalNet / highExpected);

  // Team costs
  const teamCostAvg = teamAvg * periodCost;

  // UI state
  let selectedJournal = $state<JournalEntry | null>(null);
  let journalsExpanded = $state(false);

  // Cumulative data for chart
  const cumulativeData = journals.reduce((acc, journal, i) => {
    const prevNet = i > 0 ? acc[i - 1].net : 0;
    // Calculate days elapsed (rough estimate: ~5.7 days per session over 74 days / 13 sessions)
    const daysPerSession = durationDays / journals.length;
    const daysElapsed = (i + 1) * daysPerSession;
    acc.push({
      date: journal.date,
      net: prevNet + (journal.inserted - journal.deleted),
      // Expected "before AI" line: 75 lines/day cumulative
      expected: Math.round(daysElapsed * avgRate),
    });
    return acc;
  }, [] as { date: string; net: number; expected: number }[]);

  const maxNet = Math.max(...cumulativeData.map((d) => d.net));
  const maxExpected = cumulativeData[cumulativeData.length - 1].expected;

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
    description="Productivity economics analysis: Dec 28, 2025 - Mar 12, 2026"
  >
    {#snippet actions()}
      <div class="flex items-center gap-2">
        <a
          href="/case-study/codectl"
          class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-1"
        >
          <FileCode size={16} />
          codectl
        </a>
        <a
          href="/case-study/team"
          class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-1"
        >
          <Users size={16} />
          Team Analysis
        </a>
      </div>
    {/snippet}
  </PageHeader>

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
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-text-primary">Cumulative Output</h3>
          <div class="flex items-center gap-4 text-2xs">
            <div class="flex items-center gap-1.5">
              <div class="w-3 h-0.5 bg-accent rounded"></div>
              <span class="text-text-secondary">AI-Augmented</span>
            </div>
            <div class="flex items-center gap-1.5">
              <div class="w-3 h-0.5 bg-warning rounded"></div>
              <span class="text-text-tertiary">5 Engineers (~6.2K @ team avg 24/day)</span>
            </div>
          </div>
        </div>
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
            <!-- Expected label outside SVG -->
            <div class="absolute bottom-1 left-2 flex items-center gap-2">
              <div class="px-2 py-0.5 bg-warning/20 rounded text-2xs font-medium text-warning border border-warning/30">
                5 Engineers: ~6.2K (24 lines/day × 5)
              </div>
              <div class="px-2 py-0.5 bg-surface-2 rounded text-2xs text-text-tertiary border border-border">
                24/day = Corekinect team avg (same period)
              </div>
            </div>
            <svg class="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              <!-- Grid lines -->
              {#each [25, 50, 75] as y}
                <line x1="0" y1={y} x2="100" y2={y} stroke="currentColor" stroke-width="0.2" class="text-border" />
              {/each}
              <!-- Expected 5-engineer output band (~6.2K = <1% of 700K, shown at 5% for visibility) -->
              <rect x="0" y="95" width="100" height="5" fill="rgb(var(--color-warning))" opacity="0.4" />
              <line x1="0" y1="95" x2="100" y2="95" stroke="rgb(var(--color-warning))" stroke-width="3" opacity="1" />
              <!-- Area fill -->
              <path
                d="M 0 100 {cumulativeData.map((d, i) => `L ${(i / (cumulativeData.length - 1)) * 100} ${100 - (d.net / maxNet) * 100}`).join(' ')} L 100 100 Z"
                fill="url(#gradient)"
                opacity="0.3"
              />
              <!-- AI-Augmented Line -->
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
            <span>Dec 28</span>
            <span>Jan 20</span>
            <span>Feb 15</span>
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
                  <div
                    class="absolute inset-y-0 left-0 bg-success/20 transition-all group-hover:bg-success/30"
                    style:width="{(journal.inserted / maxJournalNet) * 100}%"
                  ></div>
                  <div
                    class="absolute inset-y-0 right-0 bg-error/20 transition-all group-hover:bg-error/30"
                    style:width="{(journal.deleted / maxJournalNet) * 100}%"
                  ></div>
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

      <div class="card p-5">
        <h3 class="text-sm font-semibold text-text-primary mb-4">Team Equivalent</h3>
        <div class="space-y-4">
          <div class="text-center py-4 bg-surface-1 rounded-lg">
            <Users size={24} class="text-accent mx-auto mb-2" />
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

      <div class="card p-5 bg-accent/5 border-accent/20">
        <h3 class="text-sm font-semibold text-text-primary mb-3">Business Impact</h3>
        <ul class="space-y-2 text-sm text-text-secondary">
          <li class="flex items-start gap-2">
            <Zap size={14} class="text-success mt-0.5 shrink-0" />
            <span><strong class="text-text-primary">10.5 weeks</strong> to production-ready platform</span>
          </li>
          <li class="flex items-start gap-2">
            <TrendingUp size={14} class="text-accent mt-0.5 shrink-0" />
            <span><strong class="text-text-primary">2x test coverage</strong> (434 → 873 tests)</span>
          </li>
          <li class="flex items-start gap-2">
            <GitCommit size={14} class="text-warning mt-0.5 shrink-0" />
            <span><strong class="text-text-primary">6 product lines</strong> integrated (Alpha, ICLE, IWSCK)</span>
          </li>
          <li class="flex items-start gap-2">
            <FileCode size={14} class="text-accent mt-0.5 shrink-0" />
            <span><strong class="text-text-primary">End-to-end</strong> manufacturing workflow operational</span>
          </li>
        </ul>
      </div>
    </div>
  </div>

  <!-- Bottom summary -->
  <div class="card p-6 bg-surface-1">
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

  <!-- Development Journals Dropdown -->
  <div class="card">
    <button
      onclick={() => journalsExpanded = !journalsExpanded}
      class="w-full p-5 flex items-center justify-between text-left"
    >
      <div>
        <h3 class="text-sm font-semibold text-text-primary">Development Journals</h3>
        <p class="text-2xs text-text-tertiary mt-1">{journals.length} sessions documented</p>
      </div>
      <ChevronDown
        size={20}
        class="text-text-tertiary transition-transform {journalsExpanded ? 'rotate-180' : ''}"
      />
    </button>

    {#if journalsExpanded}
      <div class="border-t border-border">
        <div class="divide-y divide-border">
          {#each journals as journal}
            {@const net = journal.inserted - journal.deleted}
            <div class="p-4 hover:bg-surface-1 transition-colors">
              <div class="flex items-center justify-between mb-1">
                <span class="font-mono text-sm text-text-primary">{journal.date}</span>
                <div class="flex items-center gap-3 text-2xs">
                  <span class="text-success">+{formatNumber(journal.inserted)}</span>
                  <span class="text-error">-{formatNumber(journal.deleted)}</span>
                  <span class="font-medium text-accent">= +{formatNumber(net)}</span>
                </div>
              </div>
              <p class="text-sm text-text-secondary">{journal.summary}</p>
              <div class="mt-2 text-2xs text-text-tertiary">
                {journal.commits} commits
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
