/** 展示层格式化与剪贴板工具。不依赖 Svelte，可在任何地方引用。 */

export function relativeTime(iso) {
  if (!iso) return '未检测'
  const t = Date.parse(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(t)) return iso
  const diff = Date.now() - t
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  const d = Math.floor(h / 24)
  return `${d} 天前`
}

/** 邮件 Date 头去掉时区偏移与括号注释，只留可读部分。 */
export function shortDate(d) {
  if (!d) return ''
  return d.replace(/ \+0000.*/, '').replace(/ \(.*\)/, '')
}

export function statusLabel(s) {
  if (s === 'ok') return '正常'
  if (s === 'error') return '异常'
  return '未测'
}

/**
 * 取首字母做头像。发件人可能是空串、纯符号或 "名字 <addr>" 形式，
 * 直接 name[0] 在空串上会得到 undefined 再 .toUpperCase() 抛错。
 */
export function initials(name, fallback = 'M') {
  const s = String(name ?? '').trim()
  if (!s) return fallback
  const inner = s.match(/^"?([^"<]+)"?\s*</)
  const source = (inner ? inner[1] : s).trim()
  const ch = [...source].find((c) => /\p{L}|\p{N}/u.test(c))
  return ch ? ch.toUpperCase() : fallback
}

/** 秒数转 "3m20s"，用于调度器倒计时。 */
export function formatEta(sec) {
  if (sec == null) return '—'
  const s = Math.max(0, Math.floor(sec))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = s % 60
  return r ? `${m}m${r}s` : `${m}m`
}

export function formatBytes(n) {
  if (n == null) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/**
 * 复制到剪贴板。
 * navigator.clipboard 仅在安全上下文（HTTPS / localhost）可用；
 * 公网 HTTP 部署会失败，因此保留 execCommand 回退。
 */
export async function copyText(text) {
  const value = text == null ? '' : String(text)
  if (!value) throw new Error('empty')

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value)
      return
    } catch {
      // fall through
    }
  }

  const ta = document.createElement('textarea')
  ta.value = value
  ta.setAttribute('readonly', '')
  ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;opacity:0;'
  document.body.appendChild(ta)
  ta.focus()
  ta.select()
  ta.setSelectionRange(0, value.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } finally {
    document.body.removeChild(ta)
  }
  if (!ok) throw new Error('copy failed')
}
