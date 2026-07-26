<script>
  /**
   * 带 <label> 的输入控件。此前表单只有 placeholder，没有可访问名称。
   * 用 bind:value 双向绑定：<Field label="邮箱" bind:value={form.email} />
   */
  let {
    label = '',
    value = $bindable(''),
    type = 'text',
    rows = 0,
    placeholder = '',
    hint = '',
    invalid = false,
    compact = false,
    ...rest
  } = $props()

  const id = `f-${Math.random().toString(36).slice(2, 9)}`
  let isTextarea = $derived(rows > 0)
</script>

<div class="wrap">
  {#if label}
    <label class="lbl" for={id}>{label}</label>
  {/if}
  {#if isTextarea}
    <textarea
      {id}
      class="field"
      class:field-compact={compact}
      class:invalid
      {rows}
      {placeholder}
      aria-invalid={invalid || undefined}
      aria-describedby={hint ? `${id}-hint` : undefined}
      bind:value
      {...rest}
    ></textarea>
  {:else if type === 'number'}
    <input
      {id}
      class="field"
      class:field-compact={compact}
      class:invalid
      type="number"
      {placeholder}
      aria-invalid={invalid || undefined}
      aria-describedby={hint ? `${id}-hint` : undefined}
      bind:value
      {...rest}
    />
  {:else}
    <input
      {id}
      class="field"
      class:field-compact={compact}
      class:invalid
      {type}
      {placeholder}
      aria-invalid={invalid || undefined}
      aria-describedby={hint ? `${id}-hint` : undefined}
      bind:value
      {...rest}
    />
  {/if}
  {#if hint}
    <p class="hint" class:err={invalid} id="{id}-hint">{hint}</p>
  {/if}
</div>

<style>
  .wrap { display: grid; gap: 0.3rem; }
  .hint { margin: 0; font-size: 0.78rem; color: var(--ink-faint); }
  .hint.err { color: var(--vermilion); }
  .invalid {
    border-color: var(--vermilion);
    box-shadow: 0 0 0 3px var(--vermilion-glow);
  }
</style>
