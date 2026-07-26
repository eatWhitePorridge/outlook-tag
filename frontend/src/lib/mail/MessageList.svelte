<script>
  import { initials, shortDate } from '../format.js'
  import EmptyState from '../ui/EmptyState.svelte'
  import Skeleton from '../ui/Skeleton.svelte'
  import CodeChips from './CodeChips.svelte'

  /**
   * 邮件列表。两种排布：
   *   compact —— 管理端，主题 / 发件人 / 日期 / 预览，验证码靠右
   *   card    —— 公开页，头像 + 主题 + 验证码印章
   * 数据与交互（打开、键盘、复制验证码）两者一致。
   */
  let {
    messages = [],
    loading = false,
    selectedUid = null,
    variant = 'compact',
    emptyTitle = '没有邮件',
    emptyHint = '',
    emptyIcon = true,
    onopen,
  } = $props()

  let card = $derived(variant === 'card')
</script>

<div class="scroll list" class:card>
  {#if loading && !messages.length}
    <Skeleton
      count={card ? 3 : 2}
      height={card ? '64px' : '56px'}
      pad={card ? '1.25rem 1.5rem' : '1rem 0.9rem'}
      gap={card ? '0.85rem' : '0.75rem'}
    />
  {:else if !messages.length}
    <EmptyState title={emptyTitle} hint={emptyHint} icon={emptyIcon} />
  {:else}
    {#each messages as m (m.uid)}
      <div
        class="row"
        class:active={selectedUid === m.uid}
        role="button"
        tabindex="0"
        aria-label="来自 {m.from || '未知发件人'}：{m.subject || '(无主题)'}"
        onclick={() => onopen?.(m)}
        onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onopen?.(m)}
      >
        {#if card}
          <div class="avatar" aria-hidden="true">{initials(m.from)}</div>
          <div class="content">
            <div class="top">
              <span class="subject truncate">{m.subject || '(无主题)'}</span>
              {#if m.codes?.length}<span class="status-pill ok">验证码</span>{/if}
            </div>
            <div class="meta faint truncate">{m.from}</div>
            <CodeChips codes={m.codes} seal />
          </div>
        {:else}
          <div class="content">
            <div class="top">
              <span class="subject truncate">{m.subject || '(无主题)'}</span>
              {#if m.codes?.length}<span class="otp-mark">码</span>{/if}
            </div>
            <div class="sub faint">
              <span class="truncate from">{m.from}</span>
              <span class="nums date">{shortDate(m.date)}</span>
            </div>
            {#if m.body_preview}
              <p class="preview faint truncate">{m.body_preview}</p>
            {/if}
          </div>
          <CodeChips codes={m.codes} align="end" />
        {/if}
      </div>
    {/each}
  {/if}
</div>

<style>
  .list { min-height: 0; }

  .row {
    display: grid;
    align-items: start;
    cursor: pointer;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 50%, transparent);
    transition: background 150ms var(--ease);
    /* 视口外的行跳过渲染 */
    content-visibility: auto;
    contain-intrinsic-size: auto 84px;
  }
  .row:hover { background: color-mix(in srgb, var(--ink) 2.5%, transparent); }

  /* compact —— 管理端 */
  .list:not(.card) .row {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.85rem;
    padding: 0.95rem 1.35rem;
  }
  .row.active {
    background: color-mix(in srgb, var(--wood) 18%, transparent);
    box-shadow: inset 3px 0 0 var(--indigo);
  }

  /* card —— 公开页 */
  .list.card .row {
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.85rem;
    padding: 1rem 1.5rem;
  }
  .avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: color-mix(in srgb, var(--stone) 60%, white);
    color: var(--ink-muted);
    font-weight: 600; font-size: 14px;
    display: grid; place-items: center;
    flex-shrink: 0; margin-top: 0.1rem;
  }

  .content { min-width: 0; display: grid; gap: 0.25rem; }
  .top { display: flex; gap: 0.5rem; align-items: center; min-width: 0; }
  .subject { flex: 1; min-width: 0; font-weight: 500; font-size: 0.95rem; }
  .list.card .subject { font-size: 0.98rem; }
  .otp-mark {
    flex-shrink: 0;
    font-size: 0.65rem; font-weight: 700;
    padding: 0.05rem 0.3rem; border-radius: 4px;
    background: var(--vermilion); color: #fff;
  }
  .sub { display: flex; justify-content: space-between; gap: 0.85rem; font-size: 0.78rem; }
  .from { min-width: 0; flex: 1; }
  .date { flex-shrink: 0; }
  .meta { font-size: 0.82rem; }
  .preview { margin: 0.15rem 0 0; font-size: 0.82rem; max-width: 100%; color: var(--ink-muted); }
</style>
