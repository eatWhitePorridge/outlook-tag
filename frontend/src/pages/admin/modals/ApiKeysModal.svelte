<script>
  import { untrack } from 'svelte'
  import { api } from '../../../lib/api.js'
  import { relativeTime } from '../../../lib/format.js'
  import { createRequest } from '../../../lib/request.svelte.js'
  import { copyWithToast, flash } from '../../../lib/stores/toast.svelte.js'
  import ConfirmDialog from '../../../lib/ui/ConfirmDialog.svelte'
  import Modal from '../../../lib/ui/Modal.svelte'

  let { open = false, onclose, onerror } = $props()

  // 变量名避开 actions / children —— 会被 {#snippet} 的同名绑定遮蔽
  let keys = $state([])
  let newName = $state('')
  let created = $state(null) // 刚创建的明文 Key，只在内存里，关闭即丢
  let pendingDelete = $state(null)
  let busy = $state(false)
  const req = createRequest()

  $effect(() => {
    const isOpen = open
    untrack(() => {
      if (isOpen) {
        created = null
        newName = ''
        load()
      }
    })
  })

  async function load() {
    const data = await req.run((signal) => api.apiKeys({ signal }))
    if (data) keys = data
    else if (req.error) onerror?.(req.error)
  }

  async function create() {
    if (!newName.trim()) return
    busy = true
    try {
      created = await api.createApiKey(newName.trim())
      newName = ''
      await load()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }

  async function toggle(k) {
    busy = true
    try {
      await api.updateApiKey(k.id, !k.enabled)
      flash(k.enabled ? '已停用' : '已启用')
      await load()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }

  async function remove() {
    const k = pendingDelete
    if (!k) return
    busy = true
    try {
      await api.deleteApiKey(k.id)
      pendingDelete = null
      flash('已删除')
      await load()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }

  let origin = $derived(typeof location !== 'undefined' ? location.origin : '')
  let sample = $derived(
    `curl -H "X-API-Key: ${created?.key ?? '<你的 Key>'}" \\\n  "${origin}/api/v1/code?email=name+tag@outlook.com"`,
  )
  let insecure = $derived(origin.startsWith('http://') && !origin.includes('localhost'))
</script>

<Modal {open} title="API Key · 取码接口" width="720px" {onclose}>
  {#if insecure}
    <p class="warn">
      当前是明文 HTTP，API Key 会以明文经过网络。请只在可信网络内使用，并定期更换。
    </p>
  {/if}

  <div class="create-row">
    <input
      class="field field-compact"
      placeholder="用途名称，例如：注册脚本"
      aria-label="新 Key 的名称"
      bind:value={newName}
      onkeydown={(e) => e.key === 'Enter' && create()}
    />
    <button class="btn btn-sm btn-primary" type="button" disabled={busy || !newName.trim()} onclick={create}>
      生成 Key
    </button>
  </div>

  {#if created}
    <div class="fresh">
      <p class="fresh-title">「{created.name}」已生成 —— <b>只显示这一次</b>，关闭后无法再查看</p>
      <button type="button" class="code-chip key-chip" onclick={() => copyWithToast(created.key, 'Key 已复制')}>
        <span class="truncate">{created.key}</span>
        <span class="hint">点击复制</span>
      </button>
    </div>
  {/if}

  <div class="scroll key-list">
    {#each keys as k (k.id)}
      <div class="key-row" class:off={!k.enabled}>
        <div class="cell">
          <div class="name truncate">{k.name}</div>
          <div class="faint nums prefix">{k.prefix}…</div>
        </div>
        <div class="cell nums">
          <div>{k.calls} 次</div>
          <div class="faint small">{k.last_used_at ? relativeTime(k.last_used_at) : '未使用'}</div>
        </div>
        <div class="cell truncate faint small target" title={k.last_target}>{k.last_target || '—'}</div>
        <div class="cell ops">
          <button class="btn btn-sm btn-ghost" type="button" disabled={busy} onclick={() => toggle(k)}>
            {k.enabled ? '停用' : '启用'}
          </button>
          <button class="btn btn-sm btn-ghost danger" type="button" disabled={busy} onclick={() => (pendingDelete = k)}>
            删除
          </button>
        </div>
      </div>
    {:else}
      <p class="empty muted">{req.loading ? '加载中…' : '还没有 Key，先生成一个'}</p>
    {/each}
  </div>

  <div class="usage">
    <div class="usage-head">
      <span class="lbl">调用示例</span>
      <button class="btn btn-sm btn-ghost" type="button" onclick={() => copyWithToast(sample, '示例已复制')}>复制</button>
    </div>
    <pre class="sample">{sample}</pre>
    <p class="faint small note">
      支持 <code>+tag</code> 别名，只会返回发到该别名的验证码。
      可加 <code>&amp;within_minutes=5</code> 只认 5 分钟内到达的邮件，避免拿到上一轮的旧码。
      限流每个 Key 每分钟 60 次。
    </p>
  </div>

  {#snippet actions()}
    <button class="btn" type="button" onclick={onclose}>关闭</button>
  {/snippet}
</Modal>

<ConfirmDialog
  open={!!pendingDelete}
  title="删除 API Key"
  message="删除「{pendingDelete?.name ?? ''}」？"
  detail="使用该 Key 的脚本会立刻开始报 401，且无法恢复。"
  confirmLabel="删除"
  danger
  {busy}
  onconfirm={remove}
  oncancel={() => (pendingDelete = null)}
/>

<style>
  .warn {
    margin: 0;
    padding: 0.6rem 0.85rem;
    border-radius: 8px;
    background: var(--vermilion-bg);
    border: 1px solid color-mix(in srgb, var(--vermilion) 25%, transparent);
    color: var(--vermilion);
    font-size: 0.84rem;
  }

  .create-row { display: flex; gap: 0.5rem; }
  .create-row input { flex: 1; }

  .fresh {
    display: grid;
    gap: 0.5rem;
    padding: 0.85rem;
    border-radius: 10px;
    background: color-mix(in srgb, var(--moss) 8%, white);
    border: 1px solid color-mix(in srgb, var(--moss) 30%, transparent);
  }
  .fresh-title { margin: 0; font-size: 0.85rem; }
  .key-chip {
    justify-content: space-between;
    width: 100%;
    font-size: 0.82rem;
    letter-spacing: 0;
    padding: 0.5rem 0.75rem;
  }
  .key-chip .hint { font-size: 0.72rem; font-weight: 500; opacity: 0.65; flex-shrink: 0; }

  .key-list {
    max-height: 260px;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }
  .key-row {
    display: grid;
    grid-template-columns: 1.5fr 0.9fr 1.2fr auto;
    gap: 0.75rem;
    align-items: center;
    padding: 0.6rem 0.2rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 50%, transparent);
    font-size: 0.84rem;
  }
  .key-row.off { opacity: 0.5; }
  .cell { min-width: 0; }
  .name { font-weight: 500; }
  .prefix { font-size: 0.75rem; }
  .small { font-size: 0.75rem; }
  .target { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .ops { display: flex; gap: 0.2rem; }
  .ops .danger { color: var(--vermilion); }
  .empty { padding: 1.75rem; text-align: center; margin: 0; }

  .usage { display: grid; gap: 0.4rem; }
  .usage-head { display: flex; align-items: center; justify-content: space-between; }
  .sample {
    margin: 0;
    padding: 0.7rem 0.85rem;
    border-radius: 8px;
    background: color-mix(in srgb, var(--ink) 4%, white);
    border: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.76rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .note { margin: 0; line-height: 1.7; }
  .note code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: color-mix(in srgb, var(--ink) 5%, transparent);
    padding: 0.05rem 0.25rem;
    border-radius: 4px;
  }
</style>
