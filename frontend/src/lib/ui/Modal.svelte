<script>
  /**
   * 统一弹窗：backdrop 点击关闭、Esc 关闭、Tab 焦点陷阱、关闭后焦点归位。
   * 此前 Admin.svelte 里 5 处手写 modal 各自缺失其中一部分。
   */
  let {
    open = false,
    title = '',
    width = '540px',
    labelledBy = undefined,
    onclose,
    children,
    actions,
  } = $props()

  let card = $state(null)
  let restoreTo = null

  const FOCUSABLE =
    'a[href],button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'

  function focusables() {
    if (!card) return []
    return [...card.querySelectorAll(FOCUSABLE)].filter(
      (el) => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement,
    )
  }

  $effect(() => {
    if (!open) return
    restoreTo = document.activeElement
    // 等 DOM 挂好再聚焦
    const id = requestAnimationFrame(() => {
      const list = focusables()
      ;(list[0] ?? card)?.focus()
    })
    return () => {
      cancelAnimationFrame(id)
      // 关闭后把焦点还给触发它的按钮
      if (restoreTo?.isConnected) restoreTo.focus()
      restoreTo = null
    }
  })

  function onKeydown(e) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onclose?.()
      return
    }
    if (e.key !== 'Tab') return
    const list = focusables()
    if (list.length < 2) return
    const first = list[0]
    const last = list[list.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && onclose?.()}
    onkeydown={onKeydown}
  >
    <div
      class="modal-card"
      bind:this={card}
      role="dialog"
      aria-modal="true"
      aria-label={labelledBy ? undefined : title || '对话框'}
      aria-labelledby={labelledBy}
      tabindex="-1"
      style="width: min(100%, {width});"
    >
      <div class="modal-content scroll">
        {#if title}<h3 class="serif modal-title">{title}</h3>{/if}
        {@render children?.()}
        {#if actions}
          <div class="modal-actions">{@render actions()}</div>
        {/if}
      </div>
    </div>
  </div>
{/if}
