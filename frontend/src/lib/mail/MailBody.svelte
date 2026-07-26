<script>
  import { buildMailSrcdoc } from './mailHtml.js'

  let { detail, prefer = 'html' } = $props()
  let mode = $state('html') // html | text

  let hasHtml = $derived(Boolean(detail?.is_html && detail?.body))
  let hasText = $derived(Boolean(detail?.text_body || (!detail?.is_html && detail?.body)))
  let textContent = $derived(detail?.text_body || (!detail?.is_html ? detail?.body : '') || '')
  let htmlContent = $derived(detail?.is_html ? detail?.body : '')

  $effect(() => {
    if (!detail) return
    if (prefer === 'text' && hasText) mode = 'text'
    else if (prefer === 'html' && hasHtml) mode = 'html'
    else if (hasHtml) mode = 'html'
    else mode = 'text'
  })

  // lettersanitizer handles both html + text fallback
  let srcdoc = $derived(
    mode === 'html' && hasHtml
      ? buildMailSrcdoc(htmlContent, textContent)
      : buildMailSrcdoc('', textContent || htmlContent),
  )
</script>

<div class="mail-body">
  {#if hasHtml && hasText}
    <div class="mode-bar">
      <button type="button" class="tab" class:on={mode === 'html'} onclick={() => (mode = 'html')}>HTML</button>
      <button type="button" class="tab" class:on={mode === 'text'} onclick={() => (mode = 'text')}>纯文本</button>
      <span class="engine faint">lettersanitizer</span>
    </div>
  {:else}
    <div class="mode-bar slim">
      <span class="engine faint">lettersanitizer</span>
    </div>
  {/if}
  <iframe
    class="frame"
    title="邮件正文"
    sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
    referrerpolicy="no-referrer"
    srcdoc={srcdoc}
  ></iframe>
</div>

<style>
  .mail-body {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1;
    background: #ffffff;
    border-radius: 0 0 12px 12px;
    overflow: hidden;
  }
  .mode-bar {
    display: flex;
    gap: 0.3rem;
    align-items: center;
    padding: 0.45rem 0.85rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 60%, white);
  }
  .mode-bar.slim { justify-content: flex-end; }
  .tab {
    border: 0;
    background: transparent;
    border-radius: 6px;
    padding: 0.3rem 0.7rem;
    font-size: 0.8rem;
    font-weight: 500;
    color: color-mix(in srgb, var(--ink) 55%, transparent);
    transition: all 150ms var(--ease);
  }
  .tab:hover {
    color: var(--ink);
    background: color-mix(in srgb, var(--ink) 4%, transparent);
  }
  .tab.on {
    background: white;
    color: var(--ink);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  }
  .engine {
    margin-left: auto;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    opacity: 0.7;
  }
  .frame {
    flex: 1;
    width: 100%;
    min-height: min(70vh, 640px);
    border: 0;
    background: #ffffff;
  }
</style>
