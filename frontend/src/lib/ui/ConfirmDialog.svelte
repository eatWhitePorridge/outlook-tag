<script>
  import Modal from './Modal.svelte'

  /**
   * 替代 window.confirm。danger 时确认按钮为朱红；
   * requireText 用于高风险操作（如批量删除），必须原样输入才放行。
   */
  let {
    open = false,
    title = '确认操作',
    message = '',
    detail = '',
    confirmLabel = '确认',
    cancelLabel = '取消',
    danger = false,
    requireText = '',
    busy = false,
    onconfirm,
    oncancel,
  } = $props()

  let typed = $state('')

  $effect(() => {
    if (open) typed = ''
  })

  let ready = $derived(!requireText || typed.trim() === requireText)
</script>

<Modal {open} {title} width="420px" onclose={oncancel}>
  {#if message}<p class="msg">{message}</p>{/if}
  {#if detail}<p class="muted detail">{detail}</p>{/if}
  {#if requireText}
    <label class="lbl" for="confirm-text">输入 <b>{requireText}</b> 以确认</label>
    <input
      id="confirm-text"
      class="field"
      bind:value={typed}
      autocomplete="off"
      onkeydown={(e) => e.key === 'Enter' && ready && !busy && onconfirm?.()}
    />
  {/if}

  {#snippet actions()}
    <button class="btn" type="button" onclick={oncancel}>{cancelLabel}</button>
    <button
      class="btn"
      class:btn-primary={!danger}
      class:btn-danger={danger}
      type="button"
      disabled={!ready || busy}
      onclick={onconfirm}
    >{confirmLabel}</button>
  {/snippet}
</Modal>

<style>
  .msg { margin: 0; font-size: 0.95rem; line-height: 1.6; }
  .detail { margin: 0; font-size: 0.85rem; }
</style>
