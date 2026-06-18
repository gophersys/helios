<script lang="ts">
  let { data }: { data: { name: string; count: number } } = $props();
</script>

<div class="ns">
  <div class="hd"><span class="nm">{data.name}</span><span class="ct">{data.count}</span></div>
</div>

<style>
  .ns {
    width: 100%; height: 100%; box-sizing: border-box;
    background: rgba(122, 162, 247, 0.04);
    border: 1px solid #262a3d; border-radius: 12px;
  }
  .hd {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 12px; color: #9aa5ce;
    font: 600 12px/1 ui-sans-serif, system-ui, sans-serif; letter-spacing: .02em;
  }
  .nm { text-transform: lowercase; }
  .ct {
    background: #262a3d; color: #7a82a8; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600;
  }
</style>
