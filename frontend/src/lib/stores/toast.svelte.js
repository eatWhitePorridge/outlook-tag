import { copyText } from '../format.js'

/** 全局单例 toast。组件里读 `toast.msg`，调用 `flash()` 写入。 */
export const toast = $state({ msg: '' })

let timer

export function flash(msg, ms = 1600) {
  toast.msg = msg
  clearTimeout(timer)
  timer = setTimeout(() => {
    toast.msg = ''
  }, ms)
}

/** 复制 + 反馈。Admin 与 User 此前各写了一份，统一到这里。 */
export async function copyWithToast(text, label = '已复制') {
  try {
    await copyText(text)
    flash(label)
  } catch {
    flash('复制失败')
  }
}
