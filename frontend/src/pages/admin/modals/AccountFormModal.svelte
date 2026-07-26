<script>
  import Modal from '../../../lib/ui/Modal.svelte'
  import Field from '../../../lib/ui/Field.svelte'

  /** 新增与编辑合一：mode='create' 显示快速导入区，'edit' 不显示。 */
  let { open = false, mode = 'create', data = $bindable(null), busy = false, onsave, onclose } = $props()

  let isCreate = $derived(mode === 'create')
</script>

<Modal
  {open}
  title={isCreate ? '添加账号' : '编辑账号凭据'}
  {onclose}
>
  {#if data}
    {#if isCreate}
      <Field
        label="快速导入（邮箱----密码----client_id----refresh_token）"
        rows={3}
        placeholder="粘贴完整凭据，一键解析…"
        bind:value={data.raw}
      />
      <p class="faint center">— 或手动分段填写 —</p>
    {/if}
    <Field label="邮箱地址" placeholder="name@outlook.com" bind:value={data.email} />
    <Field label={isCreate ? '密码（可选）' : '密码'} placeholder="密码" bind:value={data.password} />
    <Field label="Client ID" placeholder="UUID" bind:value={data.client_id} />
    <Field label="Refresh Token" rows={2} placeholder="Refresh Token" bind:value={data.refresh_token} />
    <Field label="备注信息（可选）" placeholder="备注" bind:value={data.note} />
  {/if}

  {#snippet actions()}
    <button class="btn" type="button" onclick={onclose}>取消</button>
    <button class="btn btn-primary" type="button" disabled={busy} onclick={onsave}>
      {isCreate ? '保存账号' : '保存修改'}
    </button>
  {/snippet}
</Modal>
