import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Pond, QuarantineCase, WaterSample } from '../types'

function nowLocal() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

const empty = {
  pondId: 0,
  sampledAt: nowLocal(),
  tempC: 26,
  salinityPpt: 28,
  doMgL: 6.5,
  ph: 8.0,
  notes: '',
}

export default function WaterSamples() {
  const [ponds, setPonds] = useState<Pond[]>([])
  const [rows, setRows] = useState<WaterSample[]>([])
  const [openCases, setOpenCases] = useState<QuarantineCase[]>([])
  const [form, setForm] = useState(empty)
  const [error, setError] = useState('')

  async function load() {
    const [ps, ws, cs] = await Promise.all([
      api<Pond[]>('/api/ponds'),
      api<WaterSample[]>('/api/water-samples'),
      api<QuarantineCase[]>('/api/quarantine-cases?openOnly=true'),
    ])
    setPonds(ps)
    setRows(ws)
    setOpenCases(cs)
    if (!form.pondId && ps[0]) {
      setForm((f) => ({ ...f, pondId: ps[0].id }))
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    // 塘口有未解除卷宗时，水质样自动挂到该卷宗编号（后端同样强制校验）
    const openCase = openCases.find((c) => c.pondId === form.pondId)
    try {
      await api('/api/water-samples', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          sampledAt: new Date(form.sampledAt).toISOString(),
          caseId: openCase ? openCase.id : undefined,
        }),
      })
      setForm((f) => ({ ...empty, pondId: f.pondId, sampledAt: nowLocal() }))
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该水质样？')) return
    try {
      await api(`/api/water-samples/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  const pondLabel = (id: number) => {
    const p = ponds.find((x) => x.id === id)
    return p ? `${p.pondCode} (${p.species})` : `#${id}`
  }

  const selectedCase = openCases.find((c) => c.pondId === form.pondId)

  return (
    <div>
      <header className="page-header">
        <h1>水质采样</h1>
        <p className="muted">
          校验：溶解氧 doMgL &gt; 0，pH ∈ [6, 9]；有未解除检疫卷宗的塘口，水样自动挂到该卷宗编号
        </p>
      </header>
      {error && <div className="error">{error}</div>}

      <form className="panel form-grid" onSubmit={onSubmit}>
        <label>
          塘口
          <select
            value={form.pondId}
            onChange={(e) => setForm({ ...form, pondId: Number(e.target.value) })}
            required
          >
            {ponds.map((p) => (
              <option key={p.id} value={p.id}>
                {p.pondCode} · {p.species}
              </option>
            ))}
          </select>
          {selectedCase && (
            <span className="hint">未解除卷宗 #{selectedCase.id}，本样将挂到该卷宗</span>
          )}
        </label>
        <label>
          采样时间
          <input
            type="datetime-local"
            value={form.sampledAt}
            onChange={(e) => setForm({ ...form, sampledAt: e.target.value })}
            required
          />
        </label>
        <label>
          水温 °C
          <input
            type="number"
            step="0.1"
            value={form.tempC}
            onChange={(e) => setForm({ ...form, tempC: Number(e.target.value) })}
            required
          />
        </label>
        <label>
          盐度 ppt
          <input
            type="number"
            step="0.1"
            value={form.salinityPpt}
            onChange={(e) => setForm({ ...form, salinityPpt: Number(e.target.value) })}
            required
          />
        </label>
        <label>
          溶解氧 mg/L
          <input
            type="number"
            step="0.1"
            value={form.doMgL}
            onChange={(e) => setForm({ ...form, doMgL: Number(e.target.value) })}
            required
          />
        </label>
        <label>
          pH
          <input
            type="number"
            step="0.1"
            value={form.ph}
            onChange={(e) => setForm({ ...form, ph: Number(e.target.value) })}
            required
          />
        </label>
        <label className="span-2">
          备注
          <input
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </label>
        <button type="submit" className="btn primary">
          登记水质样
        </button>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>塘口</th>
              <th>采样时间</th>
              <th>水温</th>
              <th>盐度</th>
              <th>DO</th>
              <th>pH</th>
              <th>卷宗</th>
              <th>备注</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{pondLabel(r.pondId)}</td>
                <td>{new Date(r.sampledAt).toLocaleString()}</td>
                <td>{r.tempC}</td>
                <td>{r.salinityPpt}</td>
                <td>{r.doMgL}</td>
                <td>{r.ph}</td>
                <td>{r.caseId ? `#${r.caseId}` : '—'}</td>
                <td>{r.notes || '—'}</td>
                <td>
                  <button className="btn ghost" onClick={() => remove(r.id)}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
