<script>
  import { formatBytes, initials } from '../format.js'
  import CodeChips from './CodeChips.svelte'
  import MailBody from './MailBody.svelte'

  /**
   * 邮件详情。两种表头：
   *   compact —— 管理端，紧凑的元信息行
   *   card    —— 公开页，头像卡片 + 「提取到验证码」标签
   */
  let {
    detail = null,
    loading = false,
    variant = 'compact',
    accountId = null,
    publicToken = null,
  } = $props()

  let card = $derived(variant === 'card')

  function attachmentHref(a) {
    const base = `/api/accounts/${accountId}/messages/${detail.uid}/attachments/${a.index}`
    // public token 走 header 传不了下载导航，附件下载只对已登录管理端开放
    return publicToken ? null : base
  }
</script>

{#if loading}
  <div class="skeleton-wrap">
    <div class="skeleton sk-title"></div>
    <div class="skeleton sk-sub"></div>
    <div class="skeleton sk-body"></div>
  </div>
{:else if detail?.error}
  <div class="pad"><p class="err">{detail.error}</p></div>
{:else if detail}
  <div class="head" class:card>
    <h2 class="serif">{detail.subject || '(无主题)'}</h2>

    {#if card}
      <div class="meta-card">
        <div class="avatar" aria-hidden="true">{initials(detail.from)}</div>
        <div class="meta-info">
          <div class="from-to">
            <span class="font-medium">{detail.from}</span>
            <span class="faint">发至</span>
            <span class="font-medium">{detail.to}</span>
          </div>
          <div class="nums faint">{detail.date}</div>
        </div>
      </div>
      {#if detail.codes?.length}
        <div class="codes-bar">
          <span class="label">提取到验证码：</span>
          <CodeChips codes={detail.codes} seal />
        </div>
      {/if}
    {:else}
      <p class="meta-line muted">{detail.from}</p>
      <p class="meta-line faint">→ {detail.to}</p>
      <p class="meta-line faint nums">{detail.date}</p>
      <CodeChips codes={detail.codes} size="lg" />
    {/if}

    {#if detail.attachments?.length}
      <div class="attachments">
        <span class="label">附件 {detail.attachments.length}</span>
        <div class="att-list">
          {#each detail.attachments as a (a.index)}
            {@const href = attachmentHref(a)}
            {#if href}
              <a class="att" {href} download={a.filename} title="{a.content_type} · {formatBytes(a.size)}">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
                <span class="truncate">{a.filename}</span>
                <span class="faint nums size">{formatBytes(a.size)}</span>
              </a>
            {:else}
              <span class="att disabled" title="附件下载需在管理端登录后使用">
                <span class="truncate">{a.filename}</span>
                <span class="faint nums size">{formatBytes(a.size)}</span>
              </span>
            {/if}
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <div class="body-wrap">
    <MailBody {detail} />
  </div>
{/if}

<style>
  .head {
    padding: 1.25rem 1.5rem 1.1rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 60%, transparent);
  }
  .head h2 { margin: 0 0 0.6rem; font-size: 1.4rem; font-weight: 600; line-height: 1.35; }
  .meta-line { margin: 0.15rem 0; font-size: 0.88rem; }

  .meta-card {
    display: flex; align-items: center; gap: 0.75rem;
    margin-top: 0.65rem; padding: 0.65rem 0.85rem;
    border-radius: 8px;
    background: color-mix(in srgb, var(--paper) 60%, white);
    border: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }
  .avatar {
    width: 38px; height: 38px; border-radius: 50%;
    background: var(--ink); color: var(--paper);
    font-weight: 600; font-size: 15px;
    display: grid; place-items: center; flex-shrink: 0;
  }
  .meta-info { display: grid; gap: 0.1rem; font-size: 0.85rem; min-width: 0; }
  .font-medium { font-weight: 500; }
  .codes-bar { display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; margin-top: 0.75rem; }

  .attachments { margin-top: 0.85rem; display: grid; gap: 0.4rem; }
  .att-list { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .att {
    display: inline-flex; align-items: center; gap: 0.4rem;
    max-width: 260px;
    padding: 0.3rem 0.65rem;
    border-radius: 7px;
    border: 1px solid color-mix(in srgb, var(--stone) 85%, var(--ink));
    background: color-mix(in srgb, white 88%, var(--paper));
    font-size: 0.8rem;
    color: var(--ink);
    transition: all 150ms var(--ease);
  }
  a.att:hover {
    border-color: var(--indigo);
    background: #fff;
    box-shadow: var(--shadow-sm);
  }
  .att.disabled { opacity: 0.55; cursor: not-allowed; }
  .size { flex-shrink: 0; font-size: 0.72rem; }

  .body-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .skeleton-wrap { padding: 1.25rem 1.5rem; display: grid; gap: 0.85rem; }
  .sk-title { height: 28px; width: 65%; }
  .sk-sub { height: 18px; width: 45%; }
  .sk-body { height: 260px; margin-top: 0.5rem; }
  .pad { padding: 3rem 1rem; text-align: center; }
  .pad p { margin: 0; }
</style>
