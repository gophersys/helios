<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { ProductStageConfig } from '$lib/types/stages';
  import { createStageConfig, updateStageConfig } from '$lib/services/stages';
  import { STAGE_NAMES } from '$lib/types/stages';

  export let productId: string;
  export let stage: number;
  export let config: ProductStageConfig | undefined = undefined;

  const dispatch = createEventDispatcher();

  let saving = false;
  let error = '';

  // Form state
  let enabled = config?.enabled ?? true;
  let buildTarget = config?.buildTarget ?? '';
  let fwRepoUrl = config?.fwRepoUrl ?? '';
  let fwRepoBranch = config?.fwRepoBranch ?? '';
  let mfgRepoUrl = config?.mfgRepoUrl ?? '';
  let mfgRepoBranch = config?.mfgRepoBranch ?? '';
  let buildVariant = config?.buildVariant ?? '';
  let testDirectory = config?.testDirectory ?? '';
  let testMarker = config?.testMarker ?? '';
  let testTimeout = config?.testTimeout ?? 900;
  let priority = config?.priority ?? 50;
  let blocksMerge = config?.blocksMerge ?? false;
  let requiresFuota = config?.requiresFuota ?? false;
  let requiresBench = config?.requiresBench ?? true;
  let maxDurationSec = config?.maxDurationSec ?? 3600;
  let buildScript = config?.buildScript ?? '';
  let description = config?.description ?? '';

  async function handleSubmit() {
    saving = true;
    error = '';
    try {
      const data: Record<string, unknown> = {
        enabled,
        buildTarget: buildTarget || null,
        fwRepoUrl: fwRepoUrl || null,
        fwRepoBranch: fwRepoBranch || null,
        mfgRepoUrl: mfgRepoUrl || null,
        mfgRepoBranch: mfgRepoBranch || null,
        buildVariant: buildVariant || null,
        testDirectory: testDirectory || null,
        testMarker: testMarker || null,
        testTimeout,
        priority,
        blocksMerge,
        requiresFuota,
        requiresBench,
        maxDurationSec,
        buildScript: buildScript || null,
        description: description || null,
      };

      if (config) {
        await updateStageConfig(productId, stage, data);
      } else {
        await createStageConfig(productId, { ...data, stage, name: STAGE_NAMES[stage] });
      }
      dispatch('saved');
    } catch (e: any) {
      error = e.message || 'Failed to save';
    } finally {
      saving = false;
    }
  }
</script>

<form on:submit|preventDefault={handleSubmit} class="space-y-4">
  {#if error}
    <div class="p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>
  {/if}

  <div class="grid grid-cols-2 gap-4">
    <!-- Build Config -->
    <div class="space-y-3">
      <h4 class="font-medium text-[var(--color-text-secondary)]">Build</h4>

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Build Target</span>
        <input type="text" bind:value={buildTarget} placeholder="alpha_b0 or native_sim"
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm" />
      </label>

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Firmware Repo URL</span>
        <input type="text" bind:value={fwRepoUrl} placeholder="git@bitbucket.org:corekinect/alpha_fw.git"
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono" />
      </label>

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Branch</span>
        <input type="text" bind:value={fwRepoBranch} placeholder="concord-main"
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono" />
      </label>

      {#if stage >= 4}
        <label class="block">
          <span class="text-xs text-[var(--color-text-tertiary)]">Mfg Repo URL</span>
          <input type="text" bind:value={mfgRepoUrl} placeholder="git@bitbucket.org:corekinect/alpha_mfg_fw.git"
            class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono" />
        </label>
        <label class="block">
          <span class="text-xs text-[var(--color-text-tertiary)]">Mfg Branch</span>
          <input type="text" bind:value={mfgRepoBranch} placeholder="main"
            class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono" />
        </label>
      {/if}

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Variant</span>
        <select bind:value={buildVariant}
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm">
          <option value="">Default</option>
          <option value="debug">Debug</option>
          <option value="release">Release</option>
          <option value="mfg">Manufacturing</option>
          <option value="test">Test</option>
        </select>
      </label>
    </div>

    <!-- Test Config -->
    <div class="space-y-3">
      <h4 class="font-medium text-[var(--color-text-secondary)]">Test & Schedule</h4>

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Test Directory</span>
        <input type="text" bind:value={testDirectory} placeholder="tests/stage5/"
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono" />
      </label>

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Pytest Marker</span>
        <input type="text" bind:value={testMarker} placeholder="-m gate"
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono" />
      </label>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="text-xs text-[var(--color-text-tertiary)]">Test Timeout (s)</span>
          <input type="number" bind:value={testTimeout} min="60" max="7200"
            class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm" />
        </label>
        <label class="block">
          <span class="text-xs text-[var(--color-text-tertiary)]">Max Duration (s)</span>
          <input type="number" bind:value={maxDurationSec} min="60" max="7200"
            class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm" />
        </label>
      </div>

      <label class="block">
        <span class="text-xs text-[var(--color-text-tertiary)]">Queue Priority (0-200)</span>
        <input type="number" bind:value={priority} min="0" max="200"
          class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm" />
      </label>

      <div class="space-y-2">
        <label class="flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
          <input type="checkbox" bind:checked={blocksMerge} class="rounded" />
          Blocks merge
        </label>
        <label class="flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
          <input type="checkbox" bind:checked={requiresFuota} class="rounded" />
          Requires FUOTA
        </label>
        <label class="flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
          <input type="checkbox" bind:checked={requiresBench} class="rounded" />
          Requires test bench
        </label>
      </div>
    </div>
  </div>

  <!-- Build Script -->
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <span class="text-xs text-[var(--color-text-tertiary)]">Build Script (bash)</span>
      {#if buildScript}
        <span class="text-2xs text-[var(--color-text-tertiary)]">{buildScript.split('\n').length} lines</span>
      {/if}
    </div>
    <textarea bind:value={buildScript} rows="20" spellcheck="false" placeholder="#!/bin/bash&#10;# Build script for this stage&#10;west build ..."
      class="w-full px-4 py-3 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-mono leading-relaxed resize-y tab-size-4"
      style="min-height: 200px;"
      onkeydown={(e) => {
        if (e.key === 'Tab') {
          e.preventDefault();
          const target = e.currentTarget;
          const start = target.selectionStart;
          const end = target.selectionEnd;
          buildScript = buildScript.substring(0, start) + '  ' + buildScript.substring(end);
          // Restore cursor after Svelte updates the DOM
          requestAnimationFrame(() => { target.selectionStart = target.selectionEnd = start + 2; });
        }
      }}></textarea>

    <!-- Environment Variables Reference -->
    <details class="text-xs">
      <summary class="text-[var(--color-text-tertiary)] cursor-pointer hover:text-[var(--color-text-secondary)] select-none">
        Available environment variables
      </summary>
      <div class="mt-2 p-3 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
        <div><span class="text-[var(--color-accent)]">$BUILD_DIR</span> <span class="text-[var(--color-text-tertiary)]">— output directory</span></div>
        <div><span class="text-[var(--color-accent)]">$REPO_DIR</span> <span class="text-[var(--color-text-tertiary)]">— cloned repo path</span></div>
        <div><span class="text-[var(--color-accent)]">$COMMIT_SHA</span> <span class="text-[var(--color-text-tertiary)]">— git commit hash</span></div>
        <div><span class="text-[var(--color-accent)]">$BRANCH</span> <span class="text-[var(--color-text-tertiary)]">— git branch name</span></div>
        <div><span class="text-[var(--color-accent)]">$VARIANT</span> <span class="text-[var(--color-text-tertiary)]">— debug/release/mfg</span></div>
        <div><span class="text-[var(--color-accent)]">$BOARD</span> <span class="text-[var(--color-text-tertiary)]">— board target name</span></div>
        <div><span class="text-[var(--color-accent)]">$MTIB_REV</span> <span class="text-[var(--color-text-tertiary)]">— MTIB hardware rev</span></div>
        <div><span class="text-[var(--color-accent)]">$TARGET</span> <span class="text-[var(--color-text-tertiary)]">— app or mfg</span></div>
        <div><span class="text-[var(--color-accent)]">$OUTPUT_DIR</span> <span class="text-[var(--color-text-tertiary)]">— same as BUILD_DIR</span></div>
        <div><span class="text-[var(--color-accent)]">$VERSION_BUILD_OVERRIDE</span> <span class="text-[var(--color-text-tertiary)]">— explicit version</span></div>
        <div><span class="text-[var(--color-accent)]">$ZEPHYR_BASE</span> <span class="text-[var(--color-text-tertiary)]">— Zephyr SDK path</span></div>
        <div><span class="text-[var(--color-accent)]">$ZEPHYR_SDK_INSTALL_DIR</span> <span class="text-[var(--color-text-tertiary)]">— toolchain path</span></div>
      </div>
    </details>
  </div>

  <label class="block">
    <span class="text-xs text-[var(--color-text-tertiary)]">Description</span>
    <input type="text" bind:value={description} placeholder="Optional description..."
      class="w-full mt-1 px-3 py-1.5 rounded bg-[var(--color-surface-0)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm" />
  </label>

  <div class="flex justify-end gap-3">
    <button type="button" on:click={() => dispatch('cancel')}
      class="px-4 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors">
      Cancel
    </button>
    <button type="submit" disabled={saving}
      class="px-4 py-2 text-sm bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50">
      {saving ? 'Saving...' : config ? 'Save Changes' : 'Create Configuration'}
    </button>
  </div>
</form>
