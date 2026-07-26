/**
 * 异步请求状态封装，替代散落各处的 try/catch/finally。
 *
 * 每个实例只跟踪一条在途请求：再次 run() 会中止上一条，
 * 因此快速改搜索条件时不会出现旧响应盖掉新响应的竞态。
 *
 *   const list = createRequest()
 *   const data = await list.run((signal) => api.accounts(params, { signal }))
 *   if (data) accounts = data.items
 */
export function createRequest() {
  let loading = $state(false)
  let error = $state('')
  let ctrl = null

  /**
   * @param fn 接收 AbortSignal 的函数
   * @returns 成功时为返回值；失败或被中止时为 undefined（此时 error 已写入）
   */
  async function run(fn) {
    ctrl?.abort()
    const mine = new AbortController()
    ctrl = mine
    loading = true
    error = ''
    try {
      const result = await fn(mine.signal)
      return mine.signal.aborted ? undefined : result
    } catch (e) {
      if (mine.signal.aborted || e?.name === 'AbortError') return undefined
      error = e?.message || String(e)
      return undefined
    } finally {
      // 只有仍是当前请求时才复位，避免被后来者覆盖
      if (ctrl === mine) {
        loading = false
        ctrl = null
      }
    }
  }

  function abort() {
    ctrl?.abort()
    ctrl = null
    loading = false
  }

  return {
    get loading() {
      return loading
    },
    get error() {
      return error
    },
    set error(v) {
      error = v
    },
    run,
    abort,
    clear: () => {
      error = ''
    },
  }
}
