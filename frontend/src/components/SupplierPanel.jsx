import { useState } from 'react'
import { api } from '../api.js'

const CATEGORIES = [
  'MRO', 'IT Hardware', 'Electronic Components', 'IT Services',
  'Raw Materials', 'Mechanical Components', 'Logistics', 'Software Licensing',
]

export default function SupplierPanel() {
  const [form, setForm] = useState({ supplier_name: '', category: 'MRO', pilot_team: '' })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.scoreSupplier({
        supplier_name: form.supplier_name,
        category: form.category,
        pilot_team: form.pilot_team || null,
      })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const score = result?.supplier_score

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h2>Supplier Scoring — RAG-Based Evaluation</h2>
      <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
        Retrieval runs against the knowledge base before every score. No parametric-memory-only scores.
      </p>

      <div className="card" style={{ maxWidth: 520 }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div>
            <label style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>Supplier Name</label>
            <input
              value={form.supplier_name}
              onChange={e => setForm(f => ({ ...f, supplier_name: e.target.value }))}
              placeholder="e.g. Acme Industrial Supplies"
              required
            />
          </div>
          <div>
            <label style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>Category</label>
            <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
              {CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>Pilot Team (optional)</label>
            <input
              value={form.pilot_team}
              onChange={e => setForm(f => ({ ...f, pilot_team: e.target.value }))}
              placeholder="e.g. pilot-alpha"
            />
          </div>
          <button type="submit" disabled={loading}>
            {loading ? <span className="spin">⟳</span> : 'Score Supplier'}
          </button>
        </form>
      </div>

      {error && <p className="err">Error: {error}</p>}

      {score && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h2>{score.supplier}</h2>
              <span className="tag">Prompt: {score.prompt_version} · Confidence: {(score.confidence * 100).toFixed(0)}%</span>
            </div>
            <StatusBadge status={score.status} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
            {['reliability', 'compliance', 'cost', 'risk', 'fit'].map(dim => (
              <DimCard key={dim} label={dim} data={score[dim]} />
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.75rem', background: 'var(--bg)', borderRadius: 6 }}>
            <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>Composite Score</span>
            <span style={{ fontSize: '1.5rem', fontWeight: 700, color: compositeColor(score.composite) }}>
              {score.composite?.toFixed(2)}/10
            </span>
            <span style={{ color: 'var(--muted)', fontSize: '0.78rem' }}>Input hash: {score.input_hash}</span>
          </div>

          {result.errors?.length > 0 && (
            <p className="err" style={{ marginTop: '0.5rem' }}>Warnings: {result.errors.join(', ')}</p>
          )}
        </div>
      )}

      {result && !score && (
        <div className="card">
          <pre style={{ fontSize: '0.78rem', color: 'var(--muted)', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

function DimCard({ label, data }) {
  if (!data) return null
  const pct = ((data.score / 10) * 100).toFixed(0)
  return (
    <div style={{ background: 'var(--bg)', borderRadius: 6, padding: '0.75rem' }}>
      <h3 style={{ marginBottom: '0.4rem' }}>{label}</h3>
      <div style={{ fontSize: '1.3rem', fontWeight: 700, color: scoreColor(data.score) }}>{data.score}</div>
      <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, marginTop: '0.4rem' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: scoreColor(data.score), borderRadius: 2 }} />
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--muted)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        src: {data.source_chunk}
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  const map = { preferred: 'badge-green', conditional: 'badge-blue', 'watch-list': 'badge-yellow', disqualified: 'badge-red' }
  return <span className={`badge ${map[status] || 'badge-muted'}`}>{status}</span>
}

function scoreColor(s) {
  if (s >= 7.5) return 'var(--green)'
  if (s >= 5) return 'var(--yellow)'
  return 'var(--red)'
}

function compositeColor(s) {
  if (s >= 7.5) return 'var(--green)'
  if (s >= 6) return 'var(--blue)'
  if (s >= 4) return 'var(--yellow)'
  return 'var(--red)'
}
