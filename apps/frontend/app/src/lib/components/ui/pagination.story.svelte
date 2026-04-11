<script lang="ts">
  import Pagination from './pagination.svelte';

  export let Hst: any;

  let currentPage = 1;

  function handlePageChange(p: number) {
    currentPage = p;
  }
</script>

<Hst.Story title="UI/Pagination" group="ui">
  <Hst.Variant title="Few Pages (3)">
    <div class="p-4">
      <Pagination page={currentPage} totalPages={3} onPageChange={handlePageChange} />
    </div>
  </Hst.Variant>

  <Hst.Variant title="Many Pages (20)">
    <div class="p-4">
      <Pagination page={5} totalPages={20} onPageChange={handlePageChange} />
    </div>
  </Hst.Variant>

  <Hst.Variant title="First Page">
    <div class="p-4">
      <Pagination page={1} totalPages={10} onPageChange={handlePageChange} />
    </div>
  </Hst.Variant>

  <Hst.Variant title="Last Page">
    <div class="p-4">
      <Pagination page={10} totalPages={10} onPageChange={handlePageChange} />
    </div>
  </Hst.Variant>

  <Hst.Variant title="Single Page (hidden)">
    <div class="p-4">
      <p class="text-sm text-text-tertiary mb-2">Pagination hides when totalPages = 1:</p>
      <Pagination page={1} totalPages={1} onPageChange={handlePageChange} />
    </div>
  </Hst.Variant>
</Hst.Story>
