import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Pond, QuarantineDossier } from '../types'

export default function QuarantineDossiers() {
  const [ponds, setPonds] = useState<Pond[]>([])
  const [rows, setRows] = useState<QuarantineDossier[]>([])
  const [pondId, setPondId] = useState(0)
  const [conclusion, setConclusion] = useState('')
  const [error, setError] = useState('')

  async function load() {
    const [ps, ds] = await Promise.all([
      api<Pond[]>('/api/ponds'),
      api<QuarantineDossier[]>('/api/quarantine-dossiers'),
    ])
    setPonds(ps)
    setRows(ds)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  const openPondIds = new Set(rows.filter((d) => !d.releasedAt).map((d) => d.pondId))
  const candidates = ponds.filter((p) => p.status === 'quarantine' && !openPondIds.has(p.id))
  const selectedPond = pondId || candidates[0]?.id || 0

  async function onOpen(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api('/api/quarantine-dossiers', {
        method: 'POST',
        body: JSON.stringify({ pondId: selectedPond, conclusion }),
      })
      setPondId(0)
      setConclusion('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '立案失败')
    }
  }

  async function onRelease(d: QuarantineDossier) {
    if (!confirm(`确认解除卷宗 #${d.id}？解除后塘口将改回在养。`)) return
    setError('')
    try {
      await api(`/api/quarantine-dossiers/${d.id}/release`, { method: 'POST' })
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
          仅隔离塘可立案，同塘同时只许一份未解除卷宗；解除条件：卷宗水质样 ≥ 3 份且最近一份溶氧 ≥ 5
          mg/L，解除后塘口自动改回在养
        </p>
      </header>
      {error && <div className="error">{error}</div>}

      <form className="panel form-grid" onSubmit={onOpen}>
        <label>
          隔离塘口
          <select
            value={selectedPond}
            onChange={(e) => setPondId(Number(e.target.value))}
            required
          >
            {candidates.length === 0 && <option value={0}>暂无可用隔离塘</option>}
            {candidates.map((p) => (
              <option key={p.id} value={p.id}>
                {p.pondCode} · {p.species}
              </option>
            ))}
          </select>
        </label>
        <label>
          结论摘要
          <input
            value={conclusion}
            onChange={(e) => setConclusion(e.target.value)}
            placeholder="立案原因与观察结论"
            required
          />
        </label>
        <button type="submit" className="btn primary" disabled={!selectedPond}>
          立案
        </button>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>所属塘口</th>
              <th>立案时刻</th>
              <th>解除时刻</th>
              <th>结论摘要</th>
              <th>水质样数</th>
              <th>最近 DO</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td>{pondLabel(d.pondId)}</td>
                <td>{new Date(d.openedAt).toLocaleString()}</td>
                <td>
                  {d.releasedAt ? (
                    new Date(d.releasedAt).toLocaleString()
                  ) : (
                    <span className="badge quarantine">未解除</span>
                  )}
                </td>
                <td>{d.conclusion}</td>
                <td>{d.sampleCount}</td>
                <td>{d.latestDoMgL ?? '—'}</td>
                <td>
                  {!d.releasedAt && (
                    <button
                      className="btn ghost"
                      disabled={!d.releasable}
                      title={d.releasable ? '判定通过，可解除' : '未满足解除条件'}
                      onClick={() => onRelease(d)}
                    >
                      解除
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
