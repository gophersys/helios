<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    orientation: 'horizontal' | 'vertical';
    initialSize: number;
    minSize: number;
    maxSize: number;
    /** For horizontal: sidebar/charts identity; for vertical: which panel is sized */
    id?: string;
    /** If true, dragging right shrinks (for right-side panels like charts) */
    inverted?: boolean;
    size: number;
    resizing: boolean;
  }

  let {
    orientation,
    initialSize,
    minSize,
    maxSize,
    id = '',
    inverted = false,
    size = $bindable(initialSize),
    resizing = $bindable(false),
  }: Props = $props();

  function startResize(e: MouseEvent) {
    e.preventDefault();
    resizing = true;
    const startPos = orientation === 'horizontal' ? e.clientX : e.clientY;
    const startSize = size;

    function onMove(ev: MouseEvent) {
      const currentPos = orientation === 'horizontal' ? ev.clientX : ev.clientY;
      const delta = currentPos - startPos;

      if (orientation === 'horizontal') {
        if (inverted) {
          size = Math.max(minSize, Math.min(maxSize, startSize - delta));
        } else {
          size = Math.max(minSize, Math.min(maxSize, startSize + delta));
        }
      } else {
        // Vertical: delta as percentage of parent
        const wrapper = (e.target as HTMLElement).closest('[data-resize-container]') as HTMLElement;
        if (!wrapper) return;
        const wrapperHeight = wrapper.getBoundingClientRect().height;
        const deltaPercent = (delta / wrapperHeight) * 100;
        size = Math.max(minSize, Math.min(maxSize, startSize + deltaPercent));
      }
    }

    function onUp() {
      resizing = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }

    document.body.style.cursor = orientation === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }
</script>

{#if orientation === 'horizontal'}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    onmousedown={startResize}
    class="w-3 mx-0.5 flex-shrink-0 flex items-center justify-center cursor-col-resize group rounded
      {resizing ? 'bg-accent/20' : 'hover:bg-surface-2'}"
  >
    <div class="w-0.5 h-8 rounded-full transition-colors {resizing ? 'bg-accent' : 'bg-border group-hover:bg-text-tertiary'}"></div>
  </div>
{:else}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    onmousedown={startResize}
    class="h-3 my-1 flex items-center justify-center cursor-row-resize group rounded transition-colors
      {resizing ? 'bg-accent/20' : 'hover:bg-surface-2'}"
  >
    <div class="w-16 h-1 rounded-full transition-colors {resizing ? 'bg-accent' : 'bg-border group-hover:bg-text-tertiary'}"></div>
  </div>
{/if}
