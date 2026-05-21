import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import MetricsCards from './MetricsCards.jsx'

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [history, setHistory] = useState([])
  const [audit, setAudit] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [m, h, a] = await Promise.all([
        api.getMetrics(),
        api.getMetricsHistory(7),
        api.getAuditSummary(),
      ])
      setMetrics(m)
      setHistory(h)
      setAudit(a)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <p style={{ color: 'var(--muted)' }}><span className="spin">⟳</span> Loading…</p>
  if (error) return <p className="err">Error: {error}</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Live Metrics — {metrics?.date}</h2>
        <button onClick={load}>Refresh</button>
      </div>

      {metrics && <MetricsCards metrics={metrics} />}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Agent invocations */}
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>Agent Invocations (Today)</h3>
          {metrics && Object.keys(metrics.agent_invocations).length > 0 ? (
            <table>
              <thead><tr><th>Agent</th><th>Count</th></tr></thead>
              <tbody>
                {Object.entries(metrics.agent_invocations).map(([k, v]) => (
                  <tr key={k}><td>{k}</td><td>{v}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>No invocations yet</p>}
        </div>

        {/* Audit summary */}
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>Audit Log (Recent)</h3>
          {audit?.recent?.length > 0 ? (
            <table>
              <thead><tr><th>Agent</th><th>Action</th><th>Status</th></tr></thead>
              <tbody>
                {audit.recent.map(r => (
                  <tr key={r.id}>
                    <td>{r.agent}</td>
                    <td style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>{r.action}</td>
                    <td><span className={`badge badge-${statusColor(r.status)}`}>{r.status || '—'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>No audit entries yet</p>}
        </div>
      </div>

      {/* Top backlog */}
      {metrics?.top_backlog_items?.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>Top Process Backlog Items</h3>
          <table>
            <thead>
              <tr><th>ID</th><th>Workflow</th><th>Bottleneck</th><th>Score</th><th>Action</th></tr>
            </thead>
            <tbody>
              {metrics.top_backlog_items.map(b => (
                <tr key={b.finding_id}>
                  <td><code style={{ fontSize: '0.78rem' }}>{b.finding_id}</code></td>
                  <td>{b.workflow}</td>
                  <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.bottleneck}</td>
                  <td><ScoreBadge score={b.score} /></td>
                  <td style={{ color: 'var(--muted)', fontSize: '0.8rem', maxWidth: 180 }}>{b.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 7-day trend */}
      {history.length > 1 && (
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>7-Day Request Volume</h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', height: 80 }}>
            {[...history].reverse().map(d => {
              const max = Math.max(...history.map(x => x.requests_processed), 1)
              const h = Math.round((d.requests_processed / max) * 70)
              return (
                <div key={d.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: '100%', height: h, background: 'var(--accent)', borderRadius: '3px 3px 0 0', minHeight: 2 }} />
                  <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>{d.date.slice(5)}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function statusColor(s) {
  if (!s) return 'muted'
  if (s.includes('gap') || s.includes('error')) return 'red'
  if (s.includes('watch') || s.includes('condition')) return 'yellow'
  if (s.includes('preferred') || s.includes('routed') || s.includes('sent')) return 'green'
  return 'blue'
}

function ScoreBadge({ score }) {
  const cls = score >= 7 ? 'badge-red' : score >= 5 ? 'badge-yellow' : 'badge-muted'
  return <span className={`badge ${cls}`}>{score}/9</span>
}
