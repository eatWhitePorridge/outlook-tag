<script>
  import { api } from '../../../lib/api.js'
  import { formatEta } from '../../../lib/format.js'
  import { flash } from '../../../lib/stores/toast.svelte.js'
  import Modal from '../../../lib/ui/Modal.svelte'

  let { open = false, sys = $bindable({}), busy = false, onclose, onsaved, onerror } = $props()

  /** 与后端 schemas.SystemSettingsUpdate 的约束保持一致 */
  const LIMITS = {
    probe_interval_minutes: [1, 1440, '轮询间隔'],
    probe_batch_size: [1, 200, '每批数量'],
    probe_workers: [1, 16, '并发线程'],
    probe_stale_hours: [1, 168, '陈旧阈值'],
  }

  let saving = $state(false)

  function bad(key) {
    const [min, max] = LIMITS[key]
    const v = Number(sys[key])
    return !Number.isFinite(v) || v < min || v > max
  }

  let invalid = $derived(Object.keys(LIMITS).filter(bad))

  async function save() {
    if (invalid.length) return
    saving = true
    try {
      sys = await api.updateSystemSettings({
        probe_enabled: !!sys.probe_enabled,
        probe_interval_minutes: Number(sys.probe_interval_minutes),
        probe_batch_size: Number(sys.probe_batch_size),
        probe_workers: Number(sys.probe_workers),
        probe_stale_hours: Number(sys.probe_stale_hours),
      })
      flash('配置已保存')
      onsaved?.()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      saving = false
    }
  }

  async function runNow() {
    saving = true
    try {
      const r = await api.probeRunNow()
      flash(r.busy ? '探测进行中…' : `立即探测 ${r.probed}（正常 ${r.ok ?? 0}）`)
      onsaved?.()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      saving = false
    }
  }
</script>

<Modal {open} title="系统参数 · 自动化连接探测" width="580px" {onclose}>
  <p class="muted hint">后台定时巡检账号可用性，优先探测未检测、异常及最久未检的账号。</p>

  <div class="settings-grid">
    <label class="set-row">
      <span>启用后台自动探测</span>
      <input type="checkbox" bind:checked={sys.probe_enabled} />
    </label>
    {#each Object.entries(LIMITS) as [key, [min, max, label]] (key)}
      <label class="set-row">
        <span>{label}（{min}–{max}）</span>
        <input
          class="field field-compact"
          class:invalid={bad(key)}
          type="number"
          {min}
          {max}
          aria-invalid={bad(key) || undefined}
          bind:value={sys[key]}
        />
      </label>
    {/each}
  </div>

  {#if invalid.length}
    <p class="err small">超出允许范围：{invalid.map((k) => LIMITS[k][2]).join('、')}</p>
  {/if}

  <div class="sched-status nums">
    <div><span class="faint">调度器:</span> {sys.scheduler?.thread_alive ? '运行中' : '未启动'}</div>
    <div><span class="faint">上次执行:</span> {sys.scheduler?.last_run_at || '—'}</div>
    <div><span class="faint">下次约:</span> {formatEta(sys.scheduler?.next_run_in_sec)}</div>
    <div>
      <span class="faint">最近结果:</span>
      {#if sys.scheduler?.last_result}
        探测 {sys.scheduler.last_result.probed} · 正常 {sys.scheduler.last_result.ok} · 异常 {sys.scheduler.last_result.error}
      {:else}
        —
      {/if}
    </div>
    <div><span class="faint">已完成轮次:</span> {sys.scheduler?.cycle ?? 0}</div>
  </div>

  {#snippet actions()}
    <button class="btn" type="button" onclick={onclose}>关闭</button>
    <button class="btn" type="button" disabled={busy || saving} onclick={runNow}>立即跑一批</button>
    <button class="btn btn-primary" type="button" disabled={busy || saving || invalid.length > 0} onclick={save}>保存配置</button>
  {/snippet}
</Modal>

<style>
  .hint { margin: 0; font-size: 0.88rem; }
  .settings-grid { display: grid; gap: 0.75rem; margin: 0.5rem 0 0.25rem; }
  .set-row {
    display: grid; grid-template-columns: 1fr 120px;
    align-items: center; gap: 0.75rem; font-size: 0.9rem;
  }
  .set-row input[type="checkbox"] { width: 18px; height: 18px; justify-self: end; }
  .invalid { border-color: var(--vermilion); box-shadow: 0 0 0 3px var(--vermilion-glow); }
  .small { font-size: 0.8rem; }
  .sched-status {
    display: grid; gap: 0.4rem;
    padding: 0.85rem 1rem; border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 50%, white);
    font-size: 0.84rem;
  }
</style>
