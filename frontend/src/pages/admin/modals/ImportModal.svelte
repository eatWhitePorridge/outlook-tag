<script>
  import { api } from '../../../lib/api.js'
  import { flash } from '../../../lib/stores/toast.svelte.js'
  import Modal from '../../../lib/ui/Modal.svelte'

  let { open = false, onclose, ondone, onerror } = $props()

  let text = $state('')
  let result = $state(null)
  let busy = $state(false)
  let failedOnly = $state(false)

  $effect(() => {
    if (open) result = null
  })

  let rows = $derived(
    !result ? [] : failedOnly ? result.results.filter((r) => !r.ok) : result.results,
  )
  let failedCount = $derived(result ? result.total - result.ok : 0)

  async function run() {
    busy = true
    result = null
    try {
      result = await api.batchImport(text)
      // 有失败项时默认切到「只看失败」，省得在几百行里翻
      failedOnly = result.total - result.ok > 0
      flash(`导入 ${result.ok}/${result.total}`)
      ondone?.()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }
</script>

<Modal {open} title="批量导入账号" width="640px" {onclose}>
  <p class="muted hint">每行一条：<code>邮箱----密码----client_id----refresh_token</code></p>
  <label class="lbl" for="import-text">凭据列表</label>
  <textarea id="import-text" class="field" rows="8" placeholder="每行粘贴一个账号…" bind:value={text}></textarea>

  {#if result}
    <div class="result-head">
      <span class="nums">导入结果：成功 {result.ok} / 共 {result.total}</span>
      {#if failedCount > 0}
        <label class="check">
          <input type="checkbox" bind:checked={failedOnly} />
          只看失败（{failedCount}）
        </label>
      {/if}
    </div>
    <div class="scroll import-list">
      {#each rows as r, i (i)}
        <div class="import-row">
          <span class="truncate">{r.email}</span>
          <span class:err={!r.ok}>{r.ok ? 'OK' : r.error}</span>
        </div>
      {:else}
        <p class="empty muted">没有失败项</p>
      {/each}
    </div>
  {/if}

  {#snippet actions()}
    <button class="btn" type="button" onclick={onclose}>关闭</button>
    <button class="btn btn-primary" type="button" disabled={busy || !text.trim()} onclick={run}>开始导入</button>
  {/snippet}
</Modal>

<style>
  .hint { margin: 0; font-size: 0.88rem; }
  .hint code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; }
  .result-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 0.75rem; font-weight: 500; font-size: 0.88rem;
  }
  .check { display: inline-flex; align-items: center; gap: 0.35rem; font-weight: 400; }
  .import-list {
    max-height: 280px;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }
  .import-row {
    display: grid; grid-template-columns: 1.4fr 1fr; gap: 0.6rem;
    padding: 0.5rem 0.2rem; font-size: 0.84rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 50%, transparent);
  }
  .empty { padding: 1.5rem; text-align: center; margin: 0; }
</style>
