<script>
  import { onMount } from 'svelte'
  import Login from './pages/Login.svelte'
  import Admin from './pages/Admin.svelte'
  import User from './pages/User.svelte'
  import { api } from './lib/api.js'

  let path = $state(location.pathname)
  let adminReady = $state(false)
  let checking = $state(true)

  function navigate(to) {
    history.pushState({}, '', to)
    path = to
  }

  onMount(() => {
    const onPop = () => { path = location.pathname }
    window.addEventListener('popstate', onPop)
    checkAdmin()
    return () => window.removeEventListener('popstate', onPop)
  })

  async function checkAdmin() {
    checking = true
    try {
      await api.me()
      adminReady = true
    } catch {
      adminReady = false
    } finally {
      checking = false
    }
  }

  async function onLoggedIn() {
    adminReady = true
    navigate('/admin')
  }

  async function onLogout() {
    try { await api.logout() } catch {}
    adminReady = false
    navigate('/admin/login')
  }

  let isAdmin = $derived(path.startsWith('/admin'))
  let isLogin = $derived(path === '/admin/login' || path === '/admin/login/')
</script>

{#if checking && isAdmin}
  <div class="boot">
    <p class="serif">信笺</p>
    <p class="muted">正在准备…</p>
  </div>
{:else if isLogin || (isAdmin && !adminReady)}
  <Login onSuccess={onLoggedIn} />
{:else if isAdmin}
  <Admin {navigate} onLogout={onLogout} />
{:else}
  <User {navigate} />
{/if}

<style>
  .boot {
    min-height: 100%;
    display: grid;
    place-content: center;
    gap: 0.5rem;
    text-align: center;
  }
  .boot .serif { font-size: 1.5rem; margin: 0; }
  .boot .muted { margin: 0; }
</style>
