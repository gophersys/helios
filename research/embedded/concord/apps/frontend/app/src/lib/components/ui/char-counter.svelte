<script lang="ts">
  /**
   * Visible character counter shown under text inputs and textareas that
   * have a `maxlength`. Goes warning at 80% and error at 100%.
   *
   * Usage:
   *   <textarea bind:value={notes} maxlength={500} ...></textarea>
   *   <CharCounter value={notes} max={500} />
   */
  interface Props {
    value: string;
    max: number;
    /** Right-align under the field. Defaults to true. */
    align?: 'left' | 'right';
  }

  let { value, max, align = 'right' }: Props = $props();

  const len = $derived((value ?? '').length);
  const tone = $derived(
    len >= max ? 'text-error' : len >= max * 0.8 ? 'text-warning' : 'text-text-tertiary'
  );
  const justify = $derived(align === 'right' ? 'text-right' : 'text-left');
</script>

<p class="mt-1 text-2xs tabular-nums {tone} {justify}">{len} / {max}</p>
