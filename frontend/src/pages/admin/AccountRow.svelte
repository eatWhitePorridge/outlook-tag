<script>
  import { relativeTime, statusLabel } from '../../lib/format.js'
  import { copyWithToast } from '../../lib/stores/toast.svelte.js'
  import StatusDot from '../../lib/ui/StatusDot.svelte'

  let {
    account,
    active = false,
    selected = false,
    selectMode = false,
    menuOpen = false,
    onselect,
    ontoggle,
    onmenu,
    onedit,
    ondelete,
  } = $props()
</script>

<div class="acc" class:active class:picked={selected}>
  {#if selectMode}
    <label class="pick">
      <input
        type="checkbox"
        checked={selected}
        aria-label="选择 {account.email}"
        onclick={(e) => e.stopPropagation()}
        onchange={() => ontoggle?.(account)}
      />
    </label>
  {/if}

  <button type="button" class="acc-main" onclick={() => onselect?.(account)}>
    <StatusDot status={account.status} />
    <div class="acc-text">
      <div class="email truncate" title={account.email}>{account.email}</div>
      <div class="meta faint">
        <span>{statusLabel(account.status)}</span>
        <span class="sep">·</span>
        <span class="nums">{relativeTime(account.last_checked_at)}</span>
        {#if account.note}<span class="sep">·</span><span class="truncate note">{account.note}</span>{/if}
      </div>
    </div>
  </button>

  <div class="acc-more">
    <button
      type="button"
      class="icon-btn"
      aria-label="{account.email} 的更多操作"
      aria-expanded={menuOpen}
      onclick={(e) => {
        e.stopPropagation()
        onmenu?.(menuOpen ? null : account.id)
      }}
    >⋯</button>
    {#if menuOpen}
      <div class="menu" role="menu">
        <button type="button" role="menuitem" onclick={() => onedit?.(account.id)}>编辑凭据</button>
        <button type="button" role="menuitem" onclick={() => copyWithToast(account.email, '邮箱已复制')}>复制邮箱</button>
        <button type="button" role="menuitem" class="danger" onclick={() => ondelete?.(account)}>删除账号</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .acc {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 30px;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 55%, transparent);
    position: relative;
    transition: background 150ms var(--ease);
    /* 视口外的行跳过渲染，长列表滚动明显更顺 */
    content-visibility: auto;
    contain-intrinsic-size: auto 58px;
  }
  .acc:has(.pick) { grid-template-columns: 30px minmax(0, 1fr) 30px; }
  .acc.active {
    background: color-mix(in srgb, var(--wood) 20%, transparent);
    box-shadow: inset 3px 0 0 var(--indigo);
  }
  .acc.picked { background: color-mix(in srgb, var(--indigo) 8%, transparent); }

  .pick { display: grid; place-items: center; padding-left: 0.55rem; }
  .pick input { width: 15px; height: 15px; }

  .acc-main {
    display: flex; gap: 0.65rem; align-items: flex-start;
    text-align: left; background: transparent; border: 0;
    padding: 0.75rem 0.4rem 0.75rem 0.9rem;
    min-width: 0; width: 100%;
  }
  .acc-main:hover { background: color-mix(in srgb, var(--ink) 2.5%, transparent); }
  .acc-text { min-width: 0; flex: 1; }
  .email { font-size: 0.86rem; font-weight: 500; line-height: 1.35; }
  .meta {
    display: flex; flex-wrap: wrap; gap: 0.15rem 0.3rem;
    font-size: 0.74rem; margin-top: 0.22rem; align-items: center;
  }
  .meta .note { max-width: 7.5rem; }
  .sep { opacity: 0.45; }

  .acc-more { position: relative; display: flex; align-items: flex-start; padding-top: 0.5rem; }

  .menu {
    position: absolute; right: 0.35rem; top: 2.2rem; z-index: 20;
    min-width: 112px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(16px);
    border: 1px solid color-mix(in srgb, var(--stone) 80%, transparent);
    border-radius: 10px;
    box-shadow: var(--shadow-lg);
    padding: 0.3rem;
    display: grid;
    gap: 0.15rem;
    animation: fadeIn 150ms var(--ease-out);
  }
  .menu button {
    border: 0; background: transparent; text-align: left;
    padding: 0.45rem 0.75rem; border-radius: 6px; font-size: 0.84rem;
    font-weight: 500; transition: background 120ms var(--ease);
  }
  .menu button:hover { background: color-mix(in srgb, var(--ink) 5%, transparent); }
  .menu button.danger { color: var(--vermilion); }
</style>
