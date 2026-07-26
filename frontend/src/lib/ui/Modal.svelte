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

  import { untrack } from 'svelte'
  import { popModal, pushModal } from '../stores/modals.svelte.js'

  let card = $state(null)
  let restoreTo = null
  let downOnBackdrop = false

  // 登记自身，供页面屏蔽全局快捷键。
  // 必须 untrack：pushModal 里的 `open += 1` 是读-改-写，
  // 不隔离的话这个 effect 会依赖自己写的值，直接 effect_update_depth_exceeded。
  $effect(() => {
    if (!open) return
    untrack(pushModal)
    return () => untrack(popModal)
  })

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
  <!--
    用 mousedown 记录起点：只有按下和松开都在遮罩上才算点击关闭。
    否则在输入框里选中文字、拖到遮罩上松手，弹窗会关掉，输入内容全丢。
  -->
  <div
    class="modal-backdrop"
    role="presentation"
    onmousedown={(e) => (downOnBackdrop = e.target === e.currentTarget)}
    onclick={(e) => {
      if (e.target === e.currentTarget && downOnBackdrop) onclose?.()
      downOnBackdrop = false
    }}
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
