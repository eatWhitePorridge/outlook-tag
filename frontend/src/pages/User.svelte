<script>
  import { api } from '../lib/api.js'
  import { initials } from '../lib/format.js'
  import { copyWithToast } from '../lib/stores/toast.svelte.js'
  import MailBody from '../lib/MailBody.svelte'

  let { navigate } = $props()
  let email = $state('')
  let error = $state('')
  let loading = $state(false)
  let session = $state(null)
  let messages = $state([])
  let page = $state(1)
  let totalPages = $state(0)
  let total = $state(0)
  let detail = $state(null)
  let detailLoading = $state(false)
  let codesOnly = $state(false)
  let view = $state('list') // list | detail

  async function lookup() {
    error = ''
    loading = true
    detail = null
    view = 'list'
    try {
      const data = await api.lookup(email.trim())
      session = data
      page = 1
      await loadMessages(1)
    } catch (err) {
      error = err.message
      session = null
    } finally {
      loading = false
    }
  }

  async function loadMessages(p = page) {
    if (!session) return
    loading = true
    try {
      const data = await api.messages(
        session.id,
        { page: p, per_page: 20, filter_to: session.filter_to, codes_only: codesOnly },
        session.token,
      )
      messages = data.messages || []
      page = data.page
      totalPages = data.total_pages
      total = data.total
    } catch (err) {
      error = err.message
    } finally {
      loading = false
    }
  }

  async function openMessage(m) {
    view = 'detail'
    detailLoading = true
    detail = null
    try {
      detail = await api.message(session.id, m.uid, session.token)
    } catch (err) {
      detail = { error: err.message }
    } finally {
      detailLoading = false
    }
  }

  function backToList() {
    view = 'list'
    detail = null
  }

  function reset() {
    session = null
    messages = []
    detail = null
    view = 'list'
    error = ''
  }

  const copyCode = (c) => copyWithToast(c, `已复制 ${c}`)
</script>

<div class="page fade-in">
  <header class="top-nav panel">
    <div class="brand">
      <div class="seal-logo" title="信笺">
        <span>信</span>
      </div>
      <div>
        <h1 class="serif logo-title">信笺</h1>
        <p class="label" style="font-size: 9.5px; margin: -2px 0 0;">Outlook Workspace</p>
      </div>
    </div>
    <div class="top-actions">
      <button class="btn btn-sm btn-ghost" type="button" onclick={() => navigate('/admin')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        管理看板
      </button>
    </div>
  </header>

  {#if !session}
    <section class="hero panel fade-in">
      <div class="hero-header">
        <div class="badge-pill">
          <span class="status-dot status-ok"></span>
          <span>即时读信 & 验证码提取</span>
        </div>
        <h2 class="serif hero-title">信件与验证码一键读取</h2>
        <p class="muted hero-sub">输入 Outlook 邮箱（`name@outlook.com`）或 `+tag` 别名（如 `name+tag@outlook.com`）实时查信。</p>
      </div>
      <div class="search-box">
        <div class="input-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
          <input
            class="field search-field"
            type="email"
            placeholder="输入邮箱地址或 +tag 别名..."
            bind:value={email}
            onkeydown={(e) => e.key === 'Enter' && lookup()}
          />
        </div>
        <button class="btn btn-primary search-btn" type="button" disabled={loading || !email.trim()} onclick={lookup}>
          {#if loading}
            <span class="spinner"></span> 查询中...
          {:else}
            读取信件
          {/if}
        </button>
      </div>

      {#if error}<p class="err-banner">{error}</p>{/if}

      <div class="quick-tips">
        <span class="faint">提示：</span>
        <span class="faint">支持 `+tag` 格式（例：`username+discord@outlook.com`）直接过滤该别名信件</span>
      </div>
    </section>
  {:else}
    <section class="inbox panel fade-in">
      {#if view === 'detail'}
        <div class="detail-view">
          <div class="detail-bar">
            <button class="btn btn-sm" type="button" onclick={backToList}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
              返回列表
            </button>
            <span class="faint truncate" style="font-size: 0.85rem;">{session.display}</span>
            <button class="btn btn-sm btn-ghost" type="button" style="margin-left: auto;" onclick={reset}>切换账号</button>
          </div>

          {#if detailLoading}
            <div class="skeleton-wrap">
              <div class="skeleton sk-title"></div>
              <div class="skeleton sk-sub"></div>
              <div class="skeleton sk-body"></div>
            </div>
          {:else if detail?.error}
            <div class="empty-state">
              <p class="err">{detail.error}</p>
            </div>
          {:else if detail}
            <div class="detail-head">
              <h2 class="serif">{detail.subject || '(无主题)'}</h2>
              <div class="meta-card">
                <div class="sender-avatar" aria-hidden="true">
                  {initials(detail.from)}
                </div>
                <div class="meta-info">
                  <div class="from-to">
                    <span class="font-medium">{detail.from}</span>
                    <span class="faint">发至</span>
                    <span class="font-medium">{detail.to}</span>
                  </div>
                  <div class="date nums faint">{detail.date}</div>
                </div>
              </div>

              {#if detail.codes?.length}
                <div class="codes-bar">
                  <span class="label">提取到验证码：</span>
                  {#each detail.codes as c}
                    <button type="button" class="code-chip" onclick={() => copyCode(c)}>
                      <span class="stamp-seal">印</span>
                      <span>{c}</span>
                    </button>
                  {/each}
                </div>
              {/if}
            </div>

            <div class="body-wrap">
              <MailBody {detail} />
            </div>
          {/if}
        </div>
      {:else}
        <div class="list-view">
          <div class="list-head">
            <div>
              <div class="list-badge">
                <span class="status-dot status-ok"></span>
                <span class="label">INBOX WORKSPACE</span>
              </div>
              <h2 class="serif truncate title-email">{session.display}</h2>
              <p class="faint nums" style="font-size: 0.82rem; margin: 0.15rem 0 0;">共收录 {total} 封信件</p>
            </div>
            <div class="actions">
              <label class="check-label">
                <input type="checkbox" bind:checked={codesOnly} onchange={() => loadMessages(1)} />
                <span>仅显示验证码</span>
              </label>
              <button class="btn btn-sm" type="button" onclick={() => loadMessages(page)}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
                刷新
              </button>
              <button class="btn btn-sm btn-ghost" type="button" onclick={reset}>切换账号</button>
            </div>
          </div>

          <div class="scroll list">
            {#if loading && !messages.length}
              <div class="skeleton-list">
                <div class="skeleton sk-item"></div>
                <div class="skeleton sk-item"></div>
                <div class="skeleton sk-item"></div>
              </div>
            {:else if !messages.length}
              <div class="empty-state">
                <svg class="enso-icon" viewBox="0 0 100 100" fill="none" stroke="currentColor">
                  <circle cx="50" cy="50" r="38" stroke-width="1.8" stroke-dasharray="210 30" stroke-linecap="round" opacity="0.3" />
                </svg>
                <p class="muted font-serif" style="font-size: 1rem;">暂无相关信件</p>
                <p class="faint" style="font-size: 0.85rem;">未在此邮箱中接收到匹配的邮件消息</p>
              </div>
            {:else}
              {#each messages as m (m.uid)}
                <div
                  class="mail-item"
                  role="button"
                  tabindex="0"
                  aria-label="来自 {m.from || '未知发件人'}：{m.subject || '(无主题)'}"
                  onclick={() => openMessage(m)}
                  onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && openMessage(m)}
                >
                  <div class="mail-avatar" aria-hidden="true">
                    {initials(m.from)}
                  </div>
                  <div class="mail-content">
                    <div class="mail-top">
                      <span class="subject truncate">{m.subject || '(无主题)'}</span>
                      {#if m.codes?.length}
                        <span class="status-pill ok">验证码</span>
                      {/if}
                    </div>
                    <div class="meta faint truncate">{m.from}</div>
                    {#if m.codes?.length}
                      <div class="codes">
                        {#each m.codes as c}
                          <button type="button" class="code-chip" aria-label="复制验证码 {c}" onclick={(e) => { e.stopPropagation(); copyCode(c) }}>
                            <span class="stamp-seal">印</span>
                            <span>{c}</span>
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            {/if}
          </div>

          {#if totalPages > 1}
            <div class="pager nums">
              <button class="btn btn-sm btn-ghost" type="button" disabled={page <= 1 || loading} onclick={() => loadMessages(page - 1)}>上一页</button>
              <span class="faint" style="font-size: 0.85rem;">{page} / {totalPages}</span>
              <button class="btn btn-sm btn-ghost" type="button" disabled={page >= totalPages || loading} onclick={() => loadMessages(page + 1)}>下一页</button>
            </div>
          {/if}
        </div>
      {/if}
    </section>
    {#if error}<p class="err-banner">{error}</p>{/if}
  {/if}
</div>


<style>
  .page {
    min-height: 100%;
    max-width: 820px;
    margin: 0 auto;
    padding: 1.5rem 1.25rem 3rem;
    display: grid;
    gap: 1.25rem;
    align-content: start;
  }

  .top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.25rem;
  }
  .brand { display: flex; align-items: center; gap: 0.75rem; }
  .seal-logo {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    background: var(--vermilion);
    color: #ffffff;
    display: grid;
    place-items: center;
    font-family: "Shippori Mincho", serif;
    font-size: 1.15rem;
    font-weight: 700;
    box-shadow: 0 3px 10px var(--vermilion-glow);
  }
  .logo-title { margin: 0; font-size: 1.45rem; font-weight: 600; line-height: 1.1; }

  .hero { padding: 2.25rem 2rem; display: grid; gap: 1.2rem; }
  .badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--moss) 10%, white);
    border: 1px solid color-mix(in srgb, var(--moss) 20%, transparent);
    font-size: 12px;
    font-weight: 500;
    color: var(--moss);
    width: fit-content;
  }
  .hero-title { margin: 0; font-size: 1.65rem; font-weight: 600; }
  .hero-sub { margin: 0; font-size: 0.95rem; line-height: 1.55; }

  .search-box { display: flex; gap: 0.65rem; flex-wrap: wrap; }
  .input-wrap {
    flex: 1 1 260px;
    position: relative;
    display: flex;
    align-items: center;
  }
  .search-icon { position: absolute; left: 0.85rem; color: var(--ink-faint); pointer-events: none; }
  .search-field { padding-left: 2.4rem; height: 44px; }
  .search-btn { height: 44px; padding: 0 1.4rem; font-size: 14.5px; }

  .quick-tips { font-size: 0.8rem; display: flex; gap: 0.35rem; align-items: center; }

  .inbox {
    min-height: 62vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .list-view, .detail-view {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .list-head, .detail-bar, .detail-head { padding: 1.25rem 1.5rem 0.9rem; }
  .detail-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }
  .list-head { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
  .list-badge { display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.15rem; }
  .title-email { margin: 0.15rem 0 0; font-weight: 600; font-size: 1.35rem; }
  .actions { display: flex; flex-wrap: wrap; gap: 0.55rem; align-items: center; }

  .check-label {
    display: inline-flex; gap: 0.45rem; align-items: center;
    font-size: 0.85rem; color: var(--ink-muted); cursor: pointer; user-select: none;
  }

  .list {
    flex: 1;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }

  .mail-item {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 55%, transparent);
    cursor: pointer;
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    transition: background 150ms var(--ease);
  }
  .mail-item:hover { background: color-mix(in srgb, var(--ink) 3%, transparent); }
  .mail-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--stone) 60%, white);
    color: var(--ink-muted);
    font-weight: 600;
    font-size: 14px;
    display: grid;
    place-items: center;
    flex-shrink: 0;
    margin-top: 0.1rem;
  }
  .mail-content { min-width: 0; flex: 1; display: grid; gap: 0.25rem; }
  .mail-top { display: flex; gap: 0.6rem; align-items: center; }
  .subject { font-weight: 500; flex: 1; min-width: 0; font-size: 0.98rem; }
  .meta { font-size: 0.82rem; }

  .codes, .codes-bar { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.35rem; }
  .codes-bar { align-items: center; margin-top: 0.75rem; }

  .pager {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.75rem 1.5rem;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }

  .body-wrap {
    flex: 1;
    min-height: 440px;
    display: flex;
    flex-direction: column;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }

  .meta-card {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.65rem;
    padding: 0.65rem 0.85rem;
    border-radius: 8px;
    background: color-mix(in srgb, var(--paper) 60%, white);
    border: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }
  .sender-avatar {
    width: 38px; height: 38px; border-radius: 50%;
    background: var(--ink); color: var(--paper);
    font-weight: 600; font-size: 15px;
    display: grid; place-items: center; flex-shrink: 0;
  }
  .meta-info { display: grid; gap: 0.1rem; font-size: 0.85rem; }

  .empty-state {
    padding: 4.5rem 1.5rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.65rem;
  }
  .enso-icon { width: 56px; height: 56px; color: var(--ink); }

  .skeleton-list, .skeleton-wrap { padding: 1.25rem 1.5rem; display: grid; gap: 0.85rem; }
  .sk-item { height: 64px; }
  .sk-title { height: 28px; width: 65%; }
  .sk-sub { height: 18px; width: 45%; }
  .sk-body { height: 260px; margin-top: 0.5rem; }

  .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .font-medium { font-weight: 500; }
  .font-serif { font-family: "Shippori Mincho", serif; }

  .err-banner {
    padding: 0.65rem 1rem;
    border-radius: 8px;
    background: var(--vermilion-bg);
    border: 1px solid color-mix(in srgb, var(--vermilion) 25%, transparent);
    color: var(--vermilion);
    font-size: 0.88rem;
    margin: 0;
  }

  .spinner {
    width: 13px; height: 13px; border: 2px solid var(--paper); border-top-color: transparent;
    border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>


