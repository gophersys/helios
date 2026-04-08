<script lang="ts">
  import { Zap, Cpu, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-svelte';
  import type { ManufacturingStageConfig } from '$lib/types/models';

  interface Props {
    stage: ManufacturingStageConfig;
    onupdate: (stage: ManufacturingStageConfig) => void;
  }

  let { stage, onupdate }: Props = $props();

  let expanded = $state(stage.enabled);

  function toggle() {
    onupdate({ ...stage, enabled: !stage.enabled });
  }

  function updateConfig(key: string, value: unknown) {
    onupdate({ ...stage, config: { ...stage.config, [key]: value } });
  }

  const stageIcons: Record<string, typeof Zap> = {
    electrical: Zap,
    flash: Cpu,
    post: ShieldCheck,
  };

  const stageLabels: Record<string, string> = {
    electrical: 'Electrical Test',
    flash: 'Firmware Flash',
    post: 'POST (Power-On Self Test)',
  };

  const stageDescriptions: Record<string, string> = {
    electrical: 'Verify power rails, bus scan, GPIO checks',
    flash: 'Program firmware via J-Link to app and comms processors',
    post: 'Boot verification, personalization, peripheral tests',
  };

  const Icon = $derived(stageIcons[stage.name] ?? Zap);
</script>

<div class="rounded-lg border border-border bg-surface-0">
  <!-- Header -->
  <div class="flex items-center gap-3 p-3">
    <label class="relative inline-flex cursor-pointer items-center">
      <input type="checkbox" checked={stage.enabled} onchange={toggle} class="peer sr-only" />
      <div class="peer h-5 w-9 rounded-full bg-surface-2 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-accent peer-checked:after:translate-x-full"></div>
    </label>
    <div class="flex h-7 w-7 items-center justify-center rounded-md {stage.enabled ? 'bg-accent/10 text-accent' : 'bg-surface-2 text-text-tertiary'}">
      <Icon size={14} />
    </div>
    <div class="flex-1 min-w-0">
      <div class="text-sm font-medium text-text-primary">{stageLabels[stage.name] ?? stage.name}</div>
      <div class="text-2xs text-text-tertiary">{stageDescriptions[stage.name] ?? ''}</div>
    </div>
    {#if stage.enabled}
      <button
        type="button"
        onclick={() => (expanded = !expanded)}
        class="rounded p-1 text-text-tertiary hover:bg-surface-2"
      >
        {#if expanded}
          <ChevronUp size={14} />
        {:else}
          <ChevronDown size={14} />
        {/if}
      </button>
    {/if}
  </div>

  <!-- Config fields -->
  {#if stage.enabled && expanded}
    <div class="border-t border-border p-3 space-y-3">
      {#if stage.name === 'electrical'}
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Ch0 Voltage (V)</span>
            <input
              type="number"
              step="0.1"
              value={stage.config.ch0Voltage ?? 4.5}
              oninput={(e) => updateConfig('ch0Voltage', parseFloat(e.currentTarget.value))}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Ch1 Voltage (V)</span>
            <input
              type="number"
              step="0.1"
              value={stage.config.ch1Voltage ?? 0}
              oninput={(e) => updateConfig('ch1Voltage', parseFloat(e.currentTarget.value))}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Min Current (mA)</span>
            <input
              type="number"
              value={stage.config.minCurrentMa ?? 5}
              oninput={(e) => updateConfig('minCurrentMa', parseInt(e.currentTarget.value))}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Max Current (mA)</span>
            <input
              type="number"
              value={stage.config.maxCurrentMa ?? 100}
              oninput={(e) => updateConfig('maxCurrentMa', parseInt(e.currentTarget.value))}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
        </div>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">I2C Bus Scan Addresses (comma-separated hex, e.g. 0x38,0x50)</span>
          <input
            type="text"
            value={stage.config.i2cAddresses ?? '0x38,0x50'}
            oninput={(e) => updateConfig('i2cAddresses', e.currentTarget.value)}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
          />
        </label>

      {:else if stage.name === 'flash'}
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              checked={stage.config.flashApp ?? true}
              onchange={(e) => updateConfig('flashApp', e.currentTarget.checked)}
              class="rounded border-border"
            />
            <span class="text-sm text-text-primary">Flash App (nRF52840)</span>
          </label>
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              checked={stage.config.flashComms ?? true}
              onchange={(e) => updateConfig('flashComms', e.currentTarget.checked)}
              class="rounded border-border"
            />
            <span class="text-sm text-text-primary">Flash Comms (nRF9151)</span>
          </label>
        </div>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">J-Link Clock Speed (kHz)</span>
          <input
            type="number"
            value={stage.config.jlinkSpeed ?? 4000}
            oninput={(e) => updateConfig('jlinkSpeed', parseInt(e.currentTarget.value))}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          />
        </label>

      {:else if stage.name === 'post'}
        <div class="space-y-2">
          <span class="block text-2xs font-medium text-text-tertiary">Enabled Substeps</span>
          <div class="grid gap-2 sm:grid-cols-2">
            {#each ['boot', 'chipId', 'bms', 'charger', 'gps', 'modem', 'imei', 'flashRW', 'personalize', 'ipcRekey'] as substep}
              <label class="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={stage.config[substep] ?? true}
                  onchange={(e) => updateConfig(substep, e.currentTarget.checked)}
                  class="rounded border-border"
                />
                <span class="text-sm text-text-primary">{substep}</span>
              </label>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
