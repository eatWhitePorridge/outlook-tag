import { sanitize } from 'lettersanitizer'

/**
 * Open-source email HTML sanitizer (lettersanitizer) + reader shell.
 * lettersanitizer: https://github.com/mat-sz/lettersanitizer
 */

const READER_CSS = `
  html { -webkit-text-size-adjust: 100%; }
  body.mail-reader {
    margin: 0;
    padding: 16px 18px 28px;
    background: #ffffff;
    color: #252525;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Zen Kaku Gothic New",
      "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: 15px;
    line-height: 1.65;
    word-break: break-word;
    overflow-wrap: anywhere;
  }
  body.mail-reader img {
    max-width: 100% !important;
    height: auto !important;
  }
  body.mail-reader table {
    max-width: 100% !important;
    border-collapse: collapse;
  }
  body.mail-reader td, body.mail-reader th {
    word-break: break-word;
  }
  body.mail-reader pre, body.mail-reader code {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.92em;
  }
  body.mail-reader a { color: #3f4a63; }
  body.mail-reader blockquote {
    margin: 0.75em 0;
    padding: 0.25em 0 0.25em 0.85em;
    border-left: 3px solid rgba(37,37,37,0.12);
    color: rgba(37,37,37,0.55);
  }
  body.mail-reader hr {
    border: 0;
    border-top: 1px solid rgba(37,37,37,0.1);
    margin: 1.25em 0;
  }
  body.mail-reader [style*="width:"] {
    max-width: 100% !important;
  }
  body.mail-reader .ExternalClass,
  body.mail-reader .ReadMsgBody { width: 100%; }
  /* lettersanitizer wrapper */
  body.mail-reader #mail-content {
    max-width: 100%;
  }
`

function rewriteLink(url) {
  try {
    const u = String(url || '').trim()
    if (!u) return '#'
    const lower = u.toLowerCase()
    if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('vbscript:')) {
      return '#'
    }
    return u
  } catch {
    return '#'
  }
}

/**
 * Sanitize email HTML/text with lettersanitizer, wrap in readable srcdoc.
 */
export function buildMailSrcdoc(html, text = '') {
  const rawHtml = html && String(html).trim() ? String(html) : ''
  const rawText = text && String(text).trim() ? String(text) : ''

  let safe = ''
  try {
    safe = sanitize(rawHtml, rawText, {
      id: 'mail-content',
      noWrapper: false,
      preserveCssPriority: true,
      allowedSchemas: ['http', 'https', 'mailto', 'cid'],
      rewriteExternalLinks: (url) => rewriteLink(url),
    })
  } catch {
    // fallback: plain text only
    safe = plainToHtml(rawText || stripTags(rawHtml) || '（无正文）')
  }

  if (!safe || !String(safe).trim()) {
    safe = plainToHtml(rawText || '（无正文）')
  }

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <base target="_blank" rel="noopener noreferrer" />
  <style>${READER_CSS}</style>
</head>
<body class="mail-reader">
${safe}
</body>
</html>`
}

export function plainToHtml(text) {
  const esc = String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const linked = esc.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  return `<pre style="margin:0;font:inherit;white-space:pre-wrap">${linked}</pre>`
}

function stripTags(html) {
  return String(html || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}
