<script lang="ts">
  import type { ProductStageConfig } from '$lib/types/stages';
  import { createStageConfig, updateStageConfig } from '$lib/services/stages';
  import { STAGE_NAMES } from '$lib/types/stages';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';

  interface Props {
    productId: string;
    stage: number;
    config?: ProductStageConfig;
    onSaved?: () => void;
    onCancel?: () => void;
  }

  let { productId, stage, config, onSaved, onCancel }: Props = $props();

  let saving = $state(false);
  let error = $state('');

  // User-editable fields only
  let enabled = $state(config?.enabled ?? true);
  let buildTarget = $state(config?.buildTarget ?? '');
  let fwRepoUrl = $state(config?.fwRepoUrl ?? '');
  let fwRepoBranch = $state(config?.fwRepoBranch ?? '');
  let mfgRepoUrl = $state(config?.mfgRepoUrl ?? '');
  let mfgRepoBranch = $state(config?.mfgRepoBranch ?? '');
  let buildVariant = $state(config?.buildVariant ?? '');
  let buildScript = $state(config?.buildScript ?? '');
  let description = $state(config?.description ?? '');

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
        buildScript: buildScript || null,
        description: description || null,
      };

      if (config) {
        await updateStageConfig(productId, stage, data);
      } else {
        await createStageConfig(productId, { ...data, stage, name: STAGE_NAMES[stage] });
      }
      onSaved?.();
    } catch (e: any) {
      error = e.message || 'Failed to save';
    } finally {
      saving = false;
    }
  }
</script>

<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
  {#if error}
    <div class="p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>
  {/if}

  <!-- Build Configuration -->
  <div class="grid grid-cols-2 gap-4">
    <div class="space-y-3">
      <label class="block">
        <span class="text-xs text-text-tertiary">Build Target</span>
        <input type="text" bind:value={buildTarget} placeholder="alpha_b0"
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm font-mono" />
      </label>

      <label class="block">
        <span class="text-xs text-text-tertiary">Variant</span>
        <select bind:value={buildVariant}
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm">
          <option value="">Default</option>
          <option value="debug">Debug</option>
          <option value="release">Release</option>
          <option value="mfg">Manufacturing</option>
          <option value="test">Test</option>
        </select>
      </label>

      <label class="block">
        <span class="text-xs text-text-tertiary">Description</span>
        <input type="text" bind:value={description} placeholder="What this stage does..."
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm" />
      </label>
    </div>

    <div class="space-y-3">
      <label class="block">
        <span class="text-xs text-text-tertiary">Firmware Repo</span>
        <input type="text" bind:value={fwRepoUrl} placeholder="git@bitbucket.org:corekinect/alpha_fw.git"
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm font-mono" />
      </label>

      <label class="block">
        <span class="text-xs text-text-tertiary">Branch</span>
        <input type="text" bind:value={fwRepoBranch} placeholder="concord-main"
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm font-mono" />
      </label>

      <label class="block">
        <span class="text-xs text-text-tertiary">Mfg Firmware Repo</span>
        <input type="text" bind:value={mfgRepoUrl} placeholder="git@bitbucket.org:corekinect/alpha_mfg_fw.git"
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm font-mono" />
      </label>

      <label class="block">
        <span class="text-xs text-text-tertiary">Mfg Branch</span>
        <input type="text" bind:value={mfgRepoBranch} placeholder="concord-main"
          class="w-full mt-1 px-3 py-1.5 rounded bg-surface-0 border border-border text-text-primary text-sm font-mono" />
      </label>
    </div>
  </div>

  <!-- Build Script -->
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <span class="text-xs text-text-tertiary">Build Script (bash)</span>
      {#if buildScript}
        <span class="text-2xs text-text-tertiary">{buildScript.split('\n').length} lines</span>
      {/if}
    </div>
    <CodeEditor value={buildScript} maxHeight="500px" onchange={(v) => buildScript = v} />

    <details class="text-xs">
      <summary class="text-text-tertiary cursor-pointer hover:text-text-secondary select-none">
        Available environment variables
      </summary>
      <div class="mt-2 p-3 rounded bg-surface-0 border border-border grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
        <div><span class="text-accent">$BUILD_DIR</span> <span class="text-text-tertiary">— output directory</span></div>
        <div><span class="text-accent">$REPO_DIR</span> <span class="text-text-tertiary">— cloned repo path</span></div>
        <div><span class="text-accent">$COMMIT_SHA</span> <span class="text-text-tertiary">— git commit hash</span></div>
        <div><span class="text-accent">$BRANCH</span> <span class="text-text-tertiary">— git branch name</span></div>
        <div><span class="text-accent">$VARIANT</span> <span class="text-text-tertiary">— debug/release/mfg</span></div>
        <div><span class="text-accent">$BOARD</span> <span class="text-text-tertiary">— board target name</span></div>
        <div><span class="text-accent">$MTIB_REV</span> <span class="text-text-tertiary">— MTIB hardware rev</span></div>
        <div><span class="text-accent">$TARGET</span> <span class="text-text-tertiary">— app or mfg</span></div>
        <div><span class="text-accent">$OUTPUT_DIR</span> <span class="text-text-tertiary">— same as BUILD_DIR</span></div>
        <div><span class="text-accent">$VERSION_BUILD_OVERRIDE</span> <span class="text-text-tertiary">— explicit version</span></div>
        <div><span class="text-accent">$ZEPHYR_BASE</span> <span class="text-text-tertiary">— Zephyr SDK path</span></div>
        <div><span class="text-accent">$ZEPHYR_SDK_INSTALL_DIR</span> <span class="text-text-tertiary">— toolchain path</span></div>
      </div>
    </details>
  </div>

  <div class="flex justify-end gap-3">
    <button type="button" onclick={() => onCancel?.()}
      class="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors">
      Cancel
    </button>
    <button type="submit" disabled={saving}
      class="px-4 py-2 text-sm bg-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50">
      {saving ? 'Saving...' : config ? 'Save Changes' : 'Create Configuration'}
    </button>
  </div>
</form>
