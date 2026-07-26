<script>
  /** 骨架屏占位。count 行、每行 height 高。 */
  let { count = 2, height = '56px', pad = '1rem 0.9rem', gap = '0.75rem' } = $props()
</script>

<div class="skeleton-list" style="padding: {pad}; gap: {gap};" aria-hidden="true">
  {#each { length: count } as _, i (i)}
    <div class="skeleton sk-item" style="height: {height};"></div>
  {/each}
</div>

<style>
  .skeleton-list { display: grid; }
</style>
