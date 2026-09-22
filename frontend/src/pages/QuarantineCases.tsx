import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Pond, QuarantineCase } from '../types'

export default function QuarantineCases() {
  const [ponds, setPonds] = useState<Pond[]>([])
  const [rows, setRows] = useState<QuarantineCase[]>([])
  const [pondId, setPondId] = useState(0)
  const [summary, setSummary] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function load() {
    const [ps, cs] = await Promise.all([
      api<Pond[]>('/api/ponds'),
      api<QuarantineCase[]>('/api/quarantine-cases'),
    ])
    setPonds(ps)
    setRows(cs)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  // 可立案的塘口：当前为隔离状态，且没有未解除卷宗
  const openPondIds = new Set(rows.filter((r) => !r.releasedAt).map((r) => r.pondId))
  const candidates = ponds.filter((p) => p.status === 'quarantine' && !openPondIds.has(p.id))

  useEffect(() => {
    if (!candidates.some((p) => p.id === pondId)) {
      setPondId(candidates[0]?.id ?? 0)
    }
  }, [rows, ponds])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setNotice('')
    try {
      await api('/api/quarantine-cases', {
        method: 'POST',
        body: JSON.stringify({ pondId, summary: summary || undefined }),
      })
      setSummary('')
      setNotice('已立案。立案后该塘新增水质样必须挂到本卷宗编号。')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '立案失败')
    }
  }

  async function release(c: QuarantineCase) {
    setError('')
    setNotice('')
    const input = window.prompt(
      `解除卷宗 #${c.id}（${pondLabel(c.pondId)}）\n可填写结论摘要，留空则保留原摘要：`,
      c.summary ?? '',
    )
    if (input === null) return
    try {
      await api(`/api/quarantine-cases/${c.id}/release`, {
        method: 'POST',
        body: JSON.stringify({ summary: input || undefined }),
      })
      setNotice(`卷宗 #${c.id} 已解除，塘口已改回在养。`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '解除失败')
    }
  }

  const pondLabel = (id: number) => {
    const p = ponds.find((x) => x.id === id)
    return p ? `${p.pondCode} (${p.species})` : `#${id}`
  }

  return (
    <div>
      <header className="page-header">
        <h1>检疫卷宗</h1>
        <p className="muted">
          仅隔离塘可立案，同塘同时只许一份未解除卷宗；解除条件：卷宗下水质样 ≥ 3 份且最近一份溶解氧 ≥ 5
          mg/L，解除后塘口自动改回在养。
        </p>
      </header>
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}

      <form className="panel form-grid" onSubmit={onSubmit}>
        <label>
          隔离塘口
          <select
            value={pondId}
            onChange={(e) => setPondId(Number(e.target.value))}
            required
            disabled={candidates.length === 0}
          >
            {candidates.length === 0 && <option value={0}>暂无可立案的隔离塘</option>}
            {candidates.map((p) => (
              <option key={p.id} value={p.id}>
                {p.pondCode} · {p.species}
              </option>
            ))}
          </select>
        </label>
        <label>
          结论摘要（立案备注，可后补）
          <input
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="如：疑似桃拉病毒携带，隔离观察"
          />
        </label>
        <button type="submit" className="btn primary" disabled={!pondId}>
          立案
        </button>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>卷宗号</th>
              <th>塘口</th>
              <th>立案时刻</th>
              <th>解除时刻</th>
              <th>水质样</th>
              <th>状态</th>
              <th>结论摘要</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td>
                <td>{pondLabel(r.pondId)}</td>
                <td>{new Date(r.openedAt).toLocaleString()}</td>
                <td>{r.releasedAt ? new Date(r.releasedAt).toLocaleString() : '—'}</td>
                <td>{r.sampleCount} / 3</td>
                <td>
                  <span className={`badge ${r.releasedAt ? 'stocked' : 'quarantine'}`}>
                    {r.releasedAt ? '已解除' : '未解除'}
                  </span>
                </td>
                <td>{r.summary || '—'}</td>
                <td>
                  {!r.releasedAt && (
                    <button className="btn ghost" onClick={() => release(r)}>
                      解除
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  暂无检疫卷宗
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
