<script>
  import { api } from '../lib/api.js'
  import { createRequest } from '../lib/request.svelte.js'
  import MailDetail from '../lib/mail/MailDetail.svelte'
  import MessageList from '../lib/mail/MessageList.svelte'
  import Pager from '../lib/ui/Pager.svelte'

  let { navigate } = $props()

  let email = $state('')
  let session = $state(null)
  let messages = $state([])
  let page = $state(1)
  let totalPages = $state(0)
  let hasMore = $state(null)
  let total = $state(0)
  let detail = $state(null)
  let selectedUid = $state(null)
  let codesOnly = $state(false)
  let view = $state('list')

  const lookupReq = createRequest()
  const listReq = createRequest()
  const detailReq = createRequest()

  let error = $derived(lookupReq.error || listReq.error)

  async function lookup() {
    detail = null
    view = 'list'
    const data = await lookupReq.run((signal) => api.lookup(email.trim(), { signal }))
    if (!data) {
      session = null
      return
    }
    session = data
    page = 1
    await loadMessages(1)
  }

  async function loadMessages(p = page) {
    if (!session) return
    const data = await listReq.run((signal) =>
      api.messages(
        session.id,
        { page: p, per_page: 20, filter_to: session.filter_to, codes_only: codesOnly },
        session.token,
        { signal },
      ),
    )
    if (!data) return
    messages = data.messages || []
    page = data.page
    totalPages = data.total_pages ?? 0
    hasMore = data.has_more ?? null
    total = data.total
  }

  async function openMessage(m) {
    selectedUid = m.uid
    view = 'detail'
    detail = null
    const data = await detailReq.run((signal) =>
      api.message(session.id, m.uid, session.token, { signal }),
    )
    if (data) detail = data
    else if (detailReq.error) detail = { error: detailReq.error }
  }

  function backToList() {
    view = 'list'
    selectedUid = null
    detail = null
  }

  function reset() {
    session = null
    messages = []
    detail = null
    selectedUid = null
    view = 'list'
    lookupReq.clear()
    listReq.clear()
  }
</script>

<div class="page fade-in">
  <header class="top-nav panel">
    <div class="brand">
      <div class="seal-logo" title="信笺"><span>信</span></div>
      <div>
        <h1 class="serif logo-title">信笺</h1>
        <p class="label" style="font-size: 9.5px; margin: -2px 0 0;">Outlook Workspace</p>
      </div>
    </div>
    <div class="top-actions">
      <button class="btn btn-sm btn-ghost" type="button" onclick={() => navigate('/admin')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        管理看板
      </button>
    </div>
  </header>

  {#if !session}
    <section class="hero panel fade-in">
      <div class="hero-header">
        <div class="badge-pill">
          <span class="status-dot status-ok"></span>
          <span>即时读信 &amp; 验证码提取</span>
        </div>
        <h2 class="serif hero-title">信件与验证码一键读取</h2>
        <p class="muted hero-sub">输入 Outlook 邮箱（`name@outlook.com`）或 `+tag` 别名（如 `name+tag@outlook.com`）实时查信。</p>
      </div>
      <div class="search-box">
        <div class="input-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
          <input
            class="field search-field"
            type="email"
            aria-label="邮箱地址或 +tag 别名"
            placeholder="输入邮箱地址或 +tag 别名..."
            bind:value={email}
            onkeydown={(e) => e.key === 'Enter' && lookup()}
          />
        </div>
        <button class="btn btn-primary search-btn" type="button" disabled={lookupReq.loading || !email.trim()} onclick={lookup}>
          {#if lookupReq.loading}
            <span class="spinner" aria-hidden="true"></span> 查询中...
          {:else}
            读取信件
          {/if}
        </button>
      </div>

      {#if error}<p class="err-banner" role="alert">{error}</p>{/if}

      <div class="quick-tips">
        <span class="faint">提示：</span>
        <span class="faint">支持 `+tag` 格式（例：`username+discord@outlook.com`）直接过滤该别名信件</span>
      </div>
    </section>
  {:else}
    <section class="inbox panel fade-in">
      {#if view === 'detail'}
        <div class="pane">
          <div class="detail-bar">
            <button class="btn btn-sm" type="button" onclick={backToList}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
              返回列表
            </button>
            <span class="faint truncate small">{session.display}</span>
            <button class="btn btn-sm btn-ghost push" type="button" onclick={reset}>切换账号</button>
          </div>
          <MailDetail
            {detail}
            loading={detailReq.loading}
            variant="card"
            accountId={session.id}
            publicToken={session.token}
          />
        </div>
      {:else}
        <div class="pane">
          <div class="list-head">
            <div>
              <div class="list-badge">
                <span class="status-dot status-ok"></span>
                <span class="label">INBOX WORKSPACE</span>
              </div>
              <h2 class="serif truncate title-email">{session.display}</h2>
              <p class="faint nums count">共收录 {total} 封信件</p>
            </div>
            <div class="actions">
              <label class="check-label">
                <input type="checkbox" bind:checked={codesOnly} onchange={() => loadMessages(1)} />
                <span>仅显示验证码</span>
              </label>
              <button class="btn btn-sm" type="button" disabled={listReq.loading} onclick={() => loadMessages(page)}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
                刷新
              </button>
              <button class="btn btn-sm btn-ghost" type="button" onclick={reset}>切换账号</button>
            </div>
          </div>

          <div class="list-wrap">
            <MessageList
              {messages}
              {selectedUid}
              loading={listReq.loading}
              variant="card"
              emptyTitle="暂无相关信件"
              emptyHint="未在此邮箱中接收到匹配的邮件消息"
              onopen={openMessage}
            />
          </div>

          {#if totalPages > 1 || hasMore !== null}
            <Pager {page} {totalPages} {hasMore} loading={listReq.loading} onchange={loadMessages} />
          {/if}
        </div>
      {/if}
    </section>
    {#if error}<p class="err-banner" role="alert">{error}</p>{/if}
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
    width: 36px; height: 36px; border-radius: 9px;
    background: var(--vermilion); color: #ffffff;
    display: grid; place-items: center;
    font-family: "Shippori Mincho", serif;
    font-size: 1.15rem; font-weight: 700;
    box-shadow: 0 3px 10px var(--vermilion-glow);
  }
  .logo-title { margin: 0; font-size: 1.45rem; font-weight: 600; line-height: 1.1; }

  .hero { padding: 2.25rem 2rem; display: grid; gap: 1.2rem; }
  .badge-pill {
    display: inline-flex; align-items: center; gap: 0.45rem;
    padding: 0.2rem 0.75rem; border-radius: 999px;
    background: color-mix(in srgb, var(--moss) 10%, white);
    border: 1px solid color-mix(in srgb, var(--moss) 20%, transparent);
    font-size: 12px; font-weight: 500; color: var(--moss);
    width: fit-content;
  }
  .hero-title { margin: 0; font-size: 1.65rem; font-weight: 600; }
  .hero-sub { margin: 0; font-size: 0.95rem; line-height: 1.55; }

  .search-box { display: flex; gap: 0.65rem; flex-wrap: wrap; }
  .input-wrap { flex: 1 1 260px; position: relative; display: flex; align-items: center; }
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
  .pane { flex: 1; min-height: 0; display: flex; flex-direction: column; }

  .list-head, .detail-bar { padding: 1.25rem 1.5rem 0.9rem; }
  .detail-bar {
    display: flex; align-items: center; gap: 0.75rem;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }
  .push { margin-left: auto; }
  .small { font-size: 0.85rem; }

  .list-head { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
  .list-badge { display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.15rem; }
  .title-email { margin: 0.15rem 0 0; font-weight: 600; font-size: 1.35rem; }
  .count { font-size: 0.82rem; margin: 0.15rem 0 0; }
  .actions { display: flex; flex-wrap: wrap; gap: 0.55rem; align-items: center; }
  .check-label {
    display: inline-flex; gap: 0.45rem; align-items: center;
    font-size: 0.85rem; color: var(--ink-muted); cursor: pointer; user-select: none;
  }

  .list-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }

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
