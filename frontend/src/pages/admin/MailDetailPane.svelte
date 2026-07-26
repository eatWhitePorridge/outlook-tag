<script>
  import MailDetail from '../../lib/mail/MailDetail.svelte'

  let {
    detail = null,
    loading = false,
    accountId = null,
    accountEmail = '',
    hasPrev = false,
    hasNext = false,
    onback,
    onprev,
    onnext,
  } = $props()
</script>

<div class="detail-view">
  <div class="detail-toolbar">
    <button class="btn btn-sm" type="button" onclick={onback}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
      返回收件箱
    </button>
    <div class="nav-pair">
      <button class="btn btn-sm btn-ghost" type="button" disabled={!hasPrev || loading} aria-label="上一封" onclick={onprev}>↑ 上一封</button>
      <button class="btn btn-sm btn-ghost" type="button" disabled={!hasNext || loading} aria-label="下一封" onclick={onnext}>↓ 下一封</button>
    </div>
    <span class="faint truncate current-mail">{accountEmail}</span>
  </div>

  <div class="detail-scroll scroll">
    <MailDetail {detail} {loading} {accountId} variant="compact" />
  </div>
</div>

<style>
  .detail-view {
    min-height: 0;
    flex: 1;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
  }
  .detail-toolbar {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.75rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 65%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }
  .nav-pair { display: flex; gap: 0.25rem; }
  .current-mail { font-size: 0.85rem; min-width: 0; margin-left: auto; }
  .detail-scroll { min-height: 0; display: flex; flex-direction: column; }
</style>
