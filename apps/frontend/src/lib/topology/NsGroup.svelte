<script lang="ts">
  // A namespace group box in the Service Map — enclosure conveys containment (no `contains` edge).
  // Token-driven (Eden light theme).
  let { data }: { data: { name: string; count: number } } = $props();
</script>

<div class="ns">
  <div class="hd"><span class="nm">{data.name}</span><span class="ct">{data.count}</span></div>
</div>

<style>
  .ns {
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 12px;
  }
  .hd {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 12px;
    color: var(--eden-app-fg);
    font: 600 12px/1 var(--font-text);
    letter-spacing: 0.02em;
  }
  .nm {
    text-transform: lowercase;
  }
  .ct {
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-code);
  }
</style>
