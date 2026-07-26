/**
 * 当前打开的弹窗计数。Modal.svelte 挂载/卸载时自行登记，
 * 页面据此屏蔽全局快捷键。
 *
 * 之前是在 Admin.svelte 里手动枚举 showAdd || showEdit || … ——
 * 每加一个弹窗就要记得改那一行，ConfirmDialog 就是这么被漏掉的。
 */
export const modals = $state({ open: 0 })

export function pushModal() {
  modals.open += 1
}

export function popModal() {
  modals.open = Math.max(0, modals.open - 1)
}
