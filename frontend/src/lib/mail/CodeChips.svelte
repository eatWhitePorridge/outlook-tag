<script>
  import { copyWithToast } from '../stores/toast.svelte.js'

  /**
   * 验证码印章。size="lg" 用于详情页，"sm" 用于列表行。
   * seal=true 时带朱印小方块（公开页样式）。
   */
  let { codes = [], size = 'sm', seal = false, align = 'start' } = $props()
</script>

{#if codes?.length}
  <div class="codes" style="justify-content: flex-{align};" class:lg={size === 'lg'}>
    {#each codes as c (c)}
      <button
        type="button"
        class="code-chip"
        class:lg={size === 'lg'}
        aria-label="复制验证码 {c}"
        onclick={(e) => {
          e.stopPropagation()
          copyWithToast(c, `已复制 ${c}`)
        }}
      >
        {#if seal}<span class="stamp-seal" aria-hidden="true">印</span>{/if}
        <span>{c}</span>
        {#if size === 'lg' && !seal}<span class="copy-hint">复制</span>{/if}
      </button>
    {/each}
  </div>
{/if}

<style>
  .codes { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .codes.lg { margin-top: 0.75rem; gap: 0.45rem; }
  .code-chip.lg { padding: 0.45rem 0.85rem; font-size: 1.05rem; gap: 0.6rem; }
  .copy-hint { font-size: 0.68rem; font-weight: 500; opacity: 0.6; letter-spacing: 0; }
</style>
