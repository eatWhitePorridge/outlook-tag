/**
 * 全局键盘快捷键。在组件 onMount 里调用，返回解绑函数。
 *
 *   onMount(() => registerKeys({ '/': focusSearch, j: next, k: prev }))
 *
 * 在输入框 / 文本域 / 可编辑区域内一律不触发，
 * 弹窗打开时也不触发（由调用方通过 enabled 控制）。
 */
const TYPING = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

export function isTyping(el = document.activeElement) {
  if (!el) return false
  return TYPING.has(el.tagName) || el.isContentEditable
}

export function registerKeys(map, { enabled = () => true } = {}) {
  function onKeydown(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return
    if (!enabled()) return

    // Esc 允许在输入框里触发（用于取消/失焦），其余键不允许
    if (e.key !== 'Escape' && isTyping()) return

    const handler = map[e.key]
    if (!handler) return
    const handled = handler(e)
    if (handled !== false) e.preventDefault()
  }

  document.addEventListener('keydown', onKeydown)
  return () => document.removeEventListener('keydown', onKeydown)
}
