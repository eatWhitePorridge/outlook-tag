<script>
  import { toast } from '../stores/toast.svelte.js'
</script>

{#if toast.msg}
  <div class="toast fade-in" role="status" aria-live="polite">{toast.msg}</div>
{/if}

<style>
  .toast {
    position: fixed;
    left: 50%;
    bottom: 1.75rem;
    transform: translateX(-50%);
    z-index: 200;
    padding: 0.65rem 1.35rem;
    border-radius: 999px;
    background: var(--ink);
    color: var(--paper);
    font-size: 0.88rem;
    font-weight: 500;
    box-shadow: var(--shadow-lg);
  }
</style>
