<script>
  /** 圆相（enso）空状态。Admin 与 User 此前各画了一份同样的 SVG。 */
  let { title = '', hint = '', icon = true, wide = false, children } = $props()
</script>

<div class="empty-state" class:wide>
  {#if icon}
    <svg class="enso-icon" viewBox="0 0 100 100" fill="none" stroke="currentColor" aria-hidden="true">
      <circle cx="50" cy="50" r="38" stroke-width="1.8" stroke-dasharray="210 30" stroke-linecap="round" opacity="0.3" />
    </svg>
  {/if}
  {#if title}<p class="serif title">{title}</p>{/if}
  {#if hint}<p class="muted hint">{hint}</p>{/if}
  {@render children?.()}
</div>

<style>
  .empty-state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    text-align: center;
    padding: 2rem;
  }
  .empty-state.wide { min-height: 50vh; }
  .enso-icon { width: 56px; height: 56px; color: var(--ink); }
  .title { font-size: 1.3rem; margin: 0.5rem 0 0; }
  .hint { font-size: 0.9rem; margin: 0; }
</style>
