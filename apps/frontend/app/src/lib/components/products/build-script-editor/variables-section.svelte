<script lang="ts">
  import { Search, Copy, Check, Variable, Terminal } from 'lucide-svelte';
  import Card from '$lib/components/ui/card.svelte';

  interface SdkVariable {
    name: string;
    description: string;
    example: string;
  }

  interface SdkFunction {
    name: string;
    description: string;
    usage: string;
  }

  interface VariableGroup {
    label: string;
    items: SdkVariable[];
  }

  const variableGroups: VariableGroup[] = [
    {
      label: 'Environment',
      items: [
        { name: '$CONCORD_PRODUCT', description: 'Product name from the Concord product catalog', example: 'alpha' },
        { name: '$CONCORD_BOARD', description: 'Board name matching the CK boards repository', example: 'alpha_b0' },
        { name: '$CONCORD_REPO_DIR', description: 'Path to the firmware repository root inside the container', example: '/workspace/firmware' },
        { name: '$CONCORD_KEYS_DIR', description: 'Directory containing signing keys for this product', example: '/workspace/keys' },
      ],
    },
    {
      label: 'Build Context',
      items: [
        { name: '$CONCORD_FW_TYPE', description: 'Firmware type being built (production or manufacturing)', example: 'app' },
        { name: '$CONCORD_VARIANT', description: 'Build variant (debug enables CONFIG_LOG, release disables)', example: 'debug' },
        { name: '$CONCORD_VERSION', description: 'Semantic version string injected into the build', example: '0.8.2' },
        { name: '$CONCORD_OUT_DIR', description: 'Output directory where collected artifacts are placed', example: '/output' },
        { name: '$CONCORD_CFW_FLAGS', description: 'CFW track flags bitmask (B/E/P + M + D)', example: '0x09' },
        { name: '$CONCORD_APP_IDS', description: 'JSON map of processor role to AppID for CFW naming', example: '{"app": 109, "comms": 108}' },
      ],
    },
  ];

  const sdkFunctions: SdkFunction[] = [
    {
      name: 'concord_init',
      description: 'Initialize the build environment. Sets up workspace paths, extracts version info, and validates the build context. Must be called before any other SDK function.',
      usage: 'concord_init',
    },
    {
      name: 'concord_collect_hex',
      description: 'Register a hex artifact for collection. The role identifies which processor this hex is for (e.g., app, comms). The hex is copied to the output directory with standardized naming.',
      usage: 'concord_collect_hex <role> <path-to-hex>',
    },
    {
      name: 'concord_collect_cfw',
      description: 'Generate an encrypted firmware (CFW) file from a signed binary. Uses the product signing key and AppID mapping to produce a properly versioned CFW artifact.',
      usage: 'concord_collect_cfw <role> <path-to-signed-bin>',
    },
    {
      name: 'concord_finalize',
      description: 'Validate all collected artifacts, generate a build.json manifest, and prepare the output directory for upload. Fails if required artifacts are missing.',
      usage: 'concord_finalize',
    },
  ];

  let searchQuery = $state('');
  let copiedName = $state<string | null>(null);

  function matchesSearch(text: string): boolean {
    if (!searchQuery) return true;
    return text.toLowerCase().includes(searchQuery.toLowerCase());
  }

  const filteredGroups = $derived(
    variableGroups.map((group) => ({
      ...group,
      items: group.items.filter(
        (v) => matchesSearch(v.name) || matchesSearch(v.description)
      ),
    })).filter((group) => group.items.length > 0)
  );

  const filteredFunctions = $derived(
    sdkFunctions.filter(
      (f) => matchesSearch(f.name) || matchesSearch(f.description)
    )
  );

  async function handleCopy(name: string): Promise<void> {
    await navigator.clipboard.writeText(name);
    copiedName = name;
    setTimeout(() => (copiedName = null), 2000);
  }
</script>

<div class="p-5 space-y-6">
  <div>
    <h3 class="text-sm font-semibold text-text-primary">SDK Variables & Functions</h3>
    <p class="mt-1 text-2xs text-text-tertiary">
      Available environment variables and SDK functions for build recipes. Click any name to copy.
    </p>
  </div>

  <!-- Search -->
  <div class="relative">
    <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
    <input
      type="text"
      bind:value={searchQuery}
      placeholder="Filter variables and functions..."
      class="w-full rounded-lg border border-border bg-surface-0 pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
    />
  </div>

  <!-- Variable groups -->
  {#each filteredGroups as group}
    <Card size="sm">
      <div class="flex items-center gap-2 mb-3">
        <Variable size={14} class="text-accent" />
        <h4 class="text-xs font-semibold text-text-secondary uppercase tracking-wider">{group.label}</h4>
      </div>
      <div class="space-y-1.5">
        {#each group.items as variable}
          <Card interactive size="sm" onclick={() => handleCopy(variable.name)} class="group !bg-surface-0 !border-border-subtle">
            <div class="flex items-center gap-2">
              <code class="text-xs font-mono font-medium text-accent">{variable.name}</code>
              <span class="opacity-0 group-hover:opacity-100 transition-opacity">
                {#if copiedName === variable.name}
                  <Check size={12} class="text-success" />
                {:else}
                  <Copy size={12} class="text-text-tertiary" />
                {/if}
              </span>
            </div>
            <p class="mt-0.5 text-2xs text-text-secondary">{variable.description}</p>
            <code class="mt-1 inline-block rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono text-text-tertiary">
              {variable.example}
            </code>
          </Card>
        {/each}
      </div>
    </Card>
  {/each}

  <!-- SDK Functions -->
  {#if filteredFunctions.length > 0}
    <Card size="sm">
      <div class="flex items-center gap-2 mb-3">
        <Terminal size={14} class="text-accent" />
        <h4 class="text-xs font-semibold text-text-secondary uppercase tracking-wider">SDK Functions</h4>
      </div>
      <div class="space-y-1.5">
        {#each filteredFunctions as func}
          <Card interactive size="sm" onclick={() => handleCopy(func.name)} class="group !bg-surface-0 !border-border-subtle">
            <div class="flex items-center gap-2">
              <code class="text-xs font-mono font-medium text-accent">{func.name}</code>
              <span class="opacity-0 group-hover:opacity-100 transition-opacity">
                {#if copiedName === func.name}
                  <Check size={12} class="text-success" />
                {:else}
                  <Copy size={12} class="text-text-tertiary" />
                {/if}
              </span>
            </div>
            <p class="mt-0.5 text-2xs text-text-secondary">{func.description}</p>
            <code class="mt-1 inline-block rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono text-text-tertiary">
              {func.usage}
            </code>
          </Card>
        {/each}
      </div>
    </Card>
  {/if}

  {#if filteredGroups.length === 0 && filteredFunctions.length === 0}
    <div class="py-8 text-center text-sm text-text-tertiary">
      No variables or functions match "{searchQuery}".
    </div>
  {/if}
</div>
