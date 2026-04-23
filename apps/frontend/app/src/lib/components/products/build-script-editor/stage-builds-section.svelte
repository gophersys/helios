<script lang="ts">
  import { Zap, Cpu, FlaskConical, Moon, Radio } from 'lucide-svelte';
  import Card from '$lib/components/ui/card.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  interface StageBuild {
    stage: string;
    description: string;
    icon: typeof Zap;
    trigger: string;
    triggerStatus: string;
    builds: {
      fwType: string;
      variant: string;
      outputs: string[];
    }[];
  }

  const stageBuilds: StageBuild[] = [
    {
      stage: 'Smoke',
      description: 'Quick validation on every PR. Verifies the build compiles and basic connectivity works.',
      icon: Zap,
      trigger: 'PR push',
      triggerStatus: 'ACTIVE',
      builds: [
        {
          fwType: 'app',
          variant: 'debug',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
      ],
    },
    {
      stage: 'Driver',
      description: 'Hardware-in-the-loop tests verifying chip functionality: power, GPIO, ADC, UART.',
      icon: Cpu,
      trigger: 'PR push',
      triggerStatus: 'ACTIVE',
      builds: [
        {
          fwType: 'app',
          variant: 'debug',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
        {
          fwType: 'mfg',
          variant: 'debug',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
      ],
    },
    {
      stage: 'Integration',
      description: 'End-to-end tests including cloud connectivity, personalization, and sensor validation.',
      icon: FlaskConical,
      trigger: 'PR push',
      triggerStatus: 'ACTIVE',
      builds: [
        {
          fwType: 'app',
          variant: 'debug',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
        {
          fwType: 'app',
          variant: 'release',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
      ],
    },
    {
      stage: 'Regression',
      description: 'Extended tests run on a schedule. Includes soak tests, memory leak detection, and stress tests.',
      icon: Moon,
      trigger: 'cron (2:00 AM)',
      triggerStatus: 'PENDING',
      builds: [
        {
          fwType: 'app',
          variant: 'debug',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
        {
          fwType: 'app',
          variant: 'release',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
        {
          fwType: 'mfg',
          variant: 'release',
          outputs: ['merged.hex (app)', 'merged.hex (comms)'],
        },
      ],
    },
    {
      stage: 'FUOTA',
      description: 'Over-the-air firmware update validation. Tests CFW delivery, MCUboot swap, and rollback.',
      icon: Radio,
      trigger: 'manual',
      triggerStatus: 'QUEUED',
      builds: [
        {
          fwType: 'app',
          variant: 'release',
          outputs: ['app_update.bin (app)', 'app_update.bin (comms)', '.cfw (app)', '.cfw (comms)'],
        },
      ],
    },
  ];
</script>

<div class="p-5 space-y-6">
  <div>
    <h3 class="text-sm font-semibold text-text-primary">Stage Build Matrix</h3>
    <p class="mt-1 text-2xs text-text-tertiary">
      Each validation stage requires specific firmware builds. Your recipe must produce all required artifacts.
    </p>
  </div>

  <div class="space-y-4">
    {#each stageBuilds as stage}
      {@const Icon = stage.icon}
      <Card size="sm" class="overflow-hidden p-0!">
        {#snippet header()}
          <div class="flex flex-1 items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10">
                <Icon size={14} class="text-accent" />
              </div>
              <div>
                <h4 class="text-xs font-semibold text-text-primary">{stage.stage}</h4>
                <p class="text-[10px] text-text-tertiary">{stage.description}</p>
              </div>
            </div>
            <StatusBadge status={stage.triggerStatus} />
          </div>
        {/snippet}

        <div class="divide-y divide-border-subtle">
          {#each stage.builds as build}
            <div class="flex items-center gap-4 px-4 py-2.5">
              <div class="flex items-center gap-2 min-w-[140px]">
                <span class="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono font-medium text-text-secondary">
                  {build.fwType}
                </span>
                <span class="rounded px-1.5 py-0.5 text-[10px] font-mono font-medium
                  {build.variant === 'debug' ? 'bg-warning-muted text-warning' : 'bg-success-muted text-success'}">
                  {build.variant}
                </span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                {#each build.outputs as output}
                  <span class="rounded border border-border-subtle bg-surface-0 px-2 py-0.5 text-[10px] font-mono text-text-tertiary">
                    {output}
                  </span>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      </Card>
    {/each}
  </div>
</div>
