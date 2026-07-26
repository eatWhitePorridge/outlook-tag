<script>
  let {
    stats = { total: 0, ok: 0, error: 0, unknown: 0, aliases: 0 },
    sys = {},
    busy = false,
    ontoggleSidebar,
    onnavigate,
    onops,
    onimport,
    onsettings,
    onprobe,
    onadd,
    onlogout,
  } = $props()
</script>

<header class="top">
  <div class="brand">
    <button class="icon-btn rail-toggle" type="button" aria-label="切换侧栏" onclick={ontoggleSidebar}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
    </button>
    <div class="seal-logo-sm" aria-hidden="true">信</div>
    <div class="brand-text">
      <h1 class="serif">信笺 · 管理控制台</h1>
      <p class="nums faint">
        <span>巡检周期: {sys.probe_enabled ? `${sys.probe_interval_minutes}m` : '禁用'}</span>
        <span class="dot">·</span>
        <span>按批: {sys.probe_batch_size}</span>
      </p>
    </div>
  </div>

  <div class="metrics-row nums">
    <div class="metric-chip"><span class="label">全部账号</span><span class="val">{stats.total}</span></div>
    <div class="metric-chip ok"><span class="label">正常连接</span><span class="val">{stats.ok}</span></div>
    <div class="metric-chip err"><span class="label">异常状态</span><span class="val">{stats.error}</span></div>
    <div class="metric-chip"><span class="label">Tag 别名</span><span class="val">{stats.aliases}</span></div>
  </div>

  <nav class="top-actions" aria-label="管理操作">
    <button class="btn btn-sm" type="button" onclick={onnavigate}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
      公开页
    </button>
    <button class="btn btn-sm" type="button" onclick={onops}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
      日志
    </button>
    <button class="btn btn-sm" type="button" onclick={onimport}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
      批量导入
    </button>
    <button class="btn btn-sm" type="button" onclick={onsettings}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"></path></svg>
      配置
    </button>
    <button class="btn btn-sm" type="button" onclick={onprobe} disabled={busy}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
      探测
    </button>
    <button class="btn btn-sm btn-primary" type="button" onclick={onadd}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
      添加
    </button>
    <button class="btn btn-sm btn-ghost" type="button" onclick={onlogout}>退出</button>
  </nav>
</header>

<style>
  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 75%, transparent);
    background: color-mix(in srgb, white 75%, var(--paper));
    backdrop-filter: blur(12px);
    z-index: 3;
  }
  .brand { display: flex; align-items: center; gap: 0.65rem; min-width: 0; }
  .seal-logo-sm {
    width: 32px; height: 32px; border-radius: 8px;
    display: grid; place-items: center; flex-shrink: 0;
    background: var(--vermilion); color: #ffffff;
    font-family: "Shippori Mincho", serif; font-size: 1rem; font-weight: 700;
    box-shadow: 0 2px 8px var(--vermilion-glow);
  }
  .brand-text h1 { margin: 0; font-size: 1.15rem; font-weight: 600; line-height: 1.2; }
  .brand-text p { margin: 0.1rem 0 0; font-size: 0.75rem; display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .dot { opacity: 0.4; }
  .rail-toggle { flex-shrink: 0; }

  .metrics-row { display: flex; gap: 0.6rem; align-items: center; }
  .metric-chip {
    display: flex; flex-direction: column;
    padding: 0.35rem 0.85rem; border-radius: 8px;
    background: color-mix(in srgb, var(--paper-glass) 80%, white);
    border: 1px solid color-mix(in srgb, var(--stone) 75%, transparent);
    min-width: 80px;
  }
  .metric-chip .label { font-size: 9.5px; opacity: 0.75; }
  .metric-chip .val { font-size: 1.15rem; font-weight: 700; line-height: 1.15; margin-top: 0.1rem; }
  .metric-chip.ok .val { color: var(--moss); }
  .metric-chip.err .val { color: var(--vermilion); }

  .top-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; justify-content: flex-end; }

  @media (max-width: 990px) {
    .metrics-row { display: none; }
  }
</style>
