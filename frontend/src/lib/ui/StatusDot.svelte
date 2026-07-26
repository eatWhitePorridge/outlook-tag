<script>
  import { statusLabel } from '../format.js'

  let { status = 'unknown' } = $props()
  let label = $derived(statusLabel(status))
</script>

<span
  class="status-dot status-{status || 'unknown'}"
  role="img"
  aria-label="连接状态：{label}"
  title={label}
></span>
