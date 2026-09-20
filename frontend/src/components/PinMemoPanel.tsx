import { createSignal, For, onMount, Show } from 'solid-js'
import { api, getUser } from '../api/client'
import type { PinMemo } from '../types'

const MAX_PINS = 3

function fmt(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

export default function PinMemoPanel(props: { roomId: number; onChanged: () => void }) {
  const [memos, setMemos] = createSignal<PinMemo[]>([])
  const [error, setError] = createSignal('')
  const [newBody, setNewBody] = createSignal('')
  const [newPinned, setNewPinned] = createSignal(true)
  const [editingId, setEditingId] = createSignal<number | null>(null)
  const [editBody, setEditBody] = createSignal('')

  const user = getUser()
  const canModify = (m: PinMemo) =>
    !!user && (user.role === 'admin' || m.authorName === user.displayName)
  const pinnedCount = () => memos().filter((m) => m.pinned).length

  async function load() {
    const list = await api<PinMemo[]>(`/api/pin-memos?roomId=${props.roomId}`)
    setMemos(list)
  }

  async function refresh() {
    await load()
    props.onChanged()
  }

  onMount(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  })

  async function add(e: Event) {
    e.preventDefault()
    setError('')
    try {
      await api('/api/pin-memos', {
        method: 'POST',
        body: JSON.stringify({ roomId: props.roomId, body: newBody(), pinned: newPinned() }),
      })
      setNewBody('')
      setNewPinned(true)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  async function setPinned(m: PinMemo, pinned: boolean) {
    setError('')
    try {
      await api(`/api/pin-memos/${m.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ pinned }),
      })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    }
  }

  function startEdit(m: PinMemo) {
    setEditingId(m.id)
    setEditBody(m.body)
  }

  async function saveBody(m: PinMemo) {
    setError('')
    try {
      await api(`/api/pin-memos/${m.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ body: editBody() }),
      })
      setEditingId(null)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <div class="memo-panel">
      <div class="memo-head">
        <span class="memo-title">置顶备忘</span>
        <span class="badge">{`已钉 ${pinnedCount()}/${MAX_PINS}`}</span>
      </div>
      {error() && <div class="error">{error()}</div>}

      <form class="memo-form" onSubmit={add}>
        <input
          value={newBody()}
          onInput={(e) => setNewBody(e.currentTarget.value)}
          maxLength={40}
          placeholder="新备忘（1–40 字）"
          required
        />
        <label class="memo-pin-check">
          <input
            type="checkbox"
            checked={newPinned()}
            onChange={(e) => setNewPinned(e.currentTarget.checked)}
          />
          置顶
        </label>
        <button type="submit" class="btn primary">
          钉上
        </button>
      </form>

      <ul class="memo-list">
        <For each={memos()}>
          {(m) => (
            <li class={`memo-item${m.pinned ? ' pinned' : ''}`}>
              <Show
                when={editingId() === m.id}
                fallback={<span class="memo-body">{m.body}</span>}
              >
                <input
                  class="memo-edit"
                  value={editBody()}
                  onInput={(e) => setEditBody(e.currentTarget.value)}
                  maxLength={40}
                />
              </Show>
              <span class="memo-meta">
                {m.authorName} · {fmt(m.createdAt)}
                <span class={`badge${m.pinned ? ' fruiting' : ''}`}>
                  {m.pinned ? '已置顶' : '未置顶'}
                </span>
              </span>
              <span class="memo-actions">
                <Show when={editingId() === m.id}>
                  <button type="button" class="btn ghost" onClick={() => saveBody(m)}>
                    保存
                  </button>
                  <button type="button" class="btn ghost" onClick={() => setEditingId(null)}>
                    取消
                  </button>
                </Show>
                <Show when={editingId() !== m.id && canModify(m)}>
                  <button type="button" class="btn ghost" onClick={() => startEdit(m)}>
                    改文
                  </button>
                </Show>
                <Show when={m.pinned && canModify(m)}>
                  <button type="button" class="btn ghost" onClick={() => setPinned(m, false)}>
                    拆钉
                  </button>
                </Show>
                <Show when={!m.pinned}>
                  <button type="button" class="btn ghost" onClick={() => setPinned(m, true)}>
                    重钉
                  </button>
                </Show>
              </span>
            </li>
          )}
        </For>
      </ul>
    </div>
  )
}
