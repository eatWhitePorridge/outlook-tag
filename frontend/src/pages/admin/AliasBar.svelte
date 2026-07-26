<script>
  import { api } from '../../lib/api.js'
  import { copyWithToast, flash } from '../../lib/stores/toast.svelte.js'

  let { accountId, aliases = [], filterTo = null, onfilter, onchanged, onerror } = $props()

  let tag = $state('')
  let busy = $state(false)

  async function create() {
    if (!accountId) return
    busy = true
    try {
      const row = await api.createAlias(accountId, tag.trim())
      tag = ''
      flash(`别名 ${row.alias}`)
      onchanged?.()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }

  async function remove(al) {
    if (!confirm(`删除别名 ${al.alias}？`)) return
    busy = true
    try {
      await api.deleteAlias(al.id)
      flash('别名已删除')
      onchanged?.(al.alias)
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }
</script>

<div class="alias-row">
  <div class="alias-chips">
    <button type="button" class="chip" class:on={!filterTo} onclick={() => onfilter?.(null)}>全部</button>
    {#each aliases as al (al.id)}
      <div class="alias-item">
        <button
          type="button"
          class="chip"
          class:on={filterTo === al.alias}
          title={al.alias}
          aria-label="只看别名 {al.alias}"
          onclick={() => onfilter?.(al.alias)}
        >+{al.tag}</button>
        <button
          type="button"
          class="mini"
          aria-label="复制别名 {al.alias}"
          disabled={busy}
          onclick={() => copyWithToast(al.alias, '别名已复制')}
        >复制</button>
        <button
          type="button"
          class="mini danger"
          aria-label="删除别名 {al.alias}"
          disabled={busy}
          onclick={() => remove(al)}
        >删</button>
      </div>
    {/each}
  </div>
  <div class="alias-add">
    <input
      class="field field-compact tag-input"
      placeholder="tag"
      aria-label="新别名标签"
      bind:value={tag}
      onkeydown={(e) => e.key === 'Enter' && create()}
    />
    <button class="btn btn-sm" type="button" disabled={busy} onclick={create}>+ 别名</button>
  </div>
</div>

<style>
  .alias-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    justify-content: space-between;
    padding: 0.65rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 55%, transparent);
    background: color-mix(in srgb, var(--paper) 55%, white);
  }
  .alias-chips {
    display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
    min-width: 0; flex: 1;
  }
  .alias-item { display: inline-flex; align-items: center; gap: 0.2rem; }
  .chip {
    border: 1px solid color-mix(in srgb, var(--stone) 85%, var(--ink));
    background: white;
    border-radius: 999px;
    padding: 0.22rem 0.65rem;
    font-size: 0.78rem;
    transition: all 150ms var(--ease);
  }
  .chip.on { background: var(--ink); color: var(--paper); border-color: var(--ink); }
  .mini {
    border: 0; background: transparent;
    font-size: 0.72rem; color: var(--ink-faint);
    padding: 0.1rem 0.25rem;
  }
  .mini:hover { color: var(--ink); }
  .mini.danger:hover { color: var(--vermilion); }
  .mini:disabled { opacity: 0.4; cursor: not-allowed; }
  .alias-add { display: flex; gap: 0.35rem; flex-shrink: 0; }
  .tag-input { width: 95px; }
</style>
