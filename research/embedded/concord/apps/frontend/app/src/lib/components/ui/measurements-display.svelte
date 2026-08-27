<script lang="ts">
  import { Check, X } from 'lucide-svelte';

  let { measurements }: { measurements: Record<string, any> | null } = $props();

  interface DisplayEntry {
    label: string;
    value: string;
    raw: unknown;
  }

  /** Replace underscores with spaces, title-case each word, preserve uppercase segments. */
  function formatLabel(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/\b([a-z])/g, (_, c) => c.toUpperCase())
      // Keep known all-caps tokens (ID, IMEI, ICCID, etc.)
      .replace(/\bId\b/g, 'ID')
      .replace(/\bImei\b/g, 'IMEI')
      .replace(/\bIccid\b/g, 'ICCID')
      .replace(/\bUuid\b/g, 'UUID')
      .replace(/\bMac\b/g, 'MAC')
      .replace(/\bSnr\b/g, 'SNR');
  }

  /** Format a numeric value with reasonable precision. */
  function formatNumber(n: number): string {
    if (Number.isInteger(n)) return n.toString();
    const abs = Math.abs(n);
    if (abs < 0.001) return n.toExponential(2);
    if (abs < 1) return n.toFixed(4);
    if (abs < 100) return n.toFixed(3);
    return n.toFixed(2);
  }

  /** Render a single value to a display string. */
  function formatValue(val: unknown): string {
    if (val === null || val === undefined) return '\u2014';

    // Structured {value, unit} object
    if (typeof val === 'object' && !Array.isArray(val) && 'value' in (val as Record<string, unknown>)) {
      const obj = val as Record<string, unknown>;
      const formatted = formatValue(obj.value);
      return obj.unit ? `${formatted} ${obj.unit}` : formatted;
    }

    if (typeof val === 'number') return formatNumber(val);
    if (typeof val === 'string') return val;
    if (typeof val === 'boolean') return ''; // handled by icon
    if (Array.isArray(val)) return val.map(v => String(v)).join(', ');

    return JSON.stringify(val);
  }

  const entries = $derived.by((): DisplayEntry[] => {
    if (!measurements || typeof measurements !== 'object') return [];
    return Object.entries(measurements).map(([key, val]) => ({
      label: formatLabel(key),
      value: formatValue(val),
      raw: typeof val === 'object' && val !== null && !Array.isArray(val) && 'value' in val
        ? (val as Record<string, unknown>).value
        : val,
    }));
  });
</script>

{#if entries.length > 0}
  <div class="bg-surface-0 rounded-lg p-2 mt-1">
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-1 text-2xs">
      {#each entries as entry (entry.label)}
        <div class="flex items-baseline gap-1 min-w-0">
          <span class="text-text-tertiary shrink-0">{entry.label}</span>
          {#if typeof entry.raw === 'boolean'}
            {#if entry.raw}
              <Check size={12} class="text-success shrink-0" />
            {:else}
              <X size={12} class="text-error shrink-0" />
            {/if}
          {:else}
            <span class="font-mono text-text-primary truncate" title={entry.value}>{entry.value}</span>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}
