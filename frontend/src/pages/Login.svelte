<script>
  import { api } from '../lib/api.js'

  let { onSuccess } = $props()
  let password = $state('')
  let error = $state('')
  let loading = $state(false)

  async function submit(e) {
    e.preventDefault()
    error = ''
    loading = true
    try {
      await api.login(password)
      onSuccess()
    } catch (err) {
      error = err.message || '登录失败'
    } finally {
      loading = false
    }
  }
</script>

<div class="wrap fade-in">
  <form class="card panel" onsubmit={submit}>
    <div class="brand">
      <div class="seal-logo">
        <span>信</span>
      </div>
      <div>
        <p class="label" style="font-size: 10px; margin: 0 0 2px;">Admin Gateway</p>
        <h1 class="serif">信笺 · 管理端</h1>
      </div>
    </div>

    <p class="muted intro">请输入系统通行口令（`ADMIN_PASSWORD`）以解锁管理面板。</p>

    <div class="field-group">
      <label class="field-label" for="pwd">通行密码</label>
      <input id="pwd" class="field" type="password" placeholder="••••••••" bind:value={password} autocomplete="current-password" />
    </div>

    {#if error}<p class="err">{error}</p>{/if}

    <button class="btn btn-primary" type="submit" disabled={loading || !password}>
      {#if loading}
        <span class="spinner"></span> 验证身份中...
      {:else}
        解封并进入管理端
      {/if}
    </button>
  </form>
</div>

<style>
  .wrap {
    min-height: 100%;
    display: grid;
    place-items: center;
    padding: 2.5rem 1.5rem;
  }
  .card {
    width: min(100%, 410px);
    padding: 2.5rem 2.2rem;
    display: grid;
    gap: 1.25rem;
    box-shadow: var(--shadow-lg);
  }
  .brand { display: flex; align-items: center; gap: 0.85rem; }
  .seal-logo {
    width: 42px;
    height: 42px;
    border-radius: 10px;
    background: var(--vermilion);
    color: #ffffff;
    display: grid;
    place-items: center;
    font-family: "Shippori Mincho", serif;
    font-size: 1.35rem;
    font-weight: 700;
    box-shadow: 0 4px 14px var(--vermilion-glow);
    flex-shrink: 0;
  }
  .brand h1 { margin: 0; font-size: 1.5rem; font-weight: 600; line-height: 1.2; }
  .intro { margin: 0; font-size: 0.9rem; line-height: 1.55; }
  .field-group { display: grid; gap: 0.4rem; }
  .field-label { font-size: 0.85rem; font-weight: 600; color: var(--ink-muted); }
  .err {
    margin: 0;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    background: var(--vermilion-bg);
    color: var(--vermilion);
    font-size: 0.85rem;
  }
  .btn { margin-top: 0.3rem; width: 100%; height: 42px; font-size: 14.5px; }
  
  .spinner {
    width: 13px; height: 13px; border: 2px solid var(--paper); border-top-color: transparent;
    border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>


