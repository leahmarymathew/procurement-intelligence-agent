import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function ProcessBacklog() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [pilotTeam, setPilotTeam] = useState('')
  const [message, setMessage] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const m = await api.getMetrics()
      setMetrics(m)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const triggerDiscovery = async () => {
    setRunning(true)
    setMessage(null)
    try {
      const r = await api.triggerDiscovery(pilotTeam || null)
      setMessage(`Process discovery triggered: ${r.message || 'running in background'}`)
      setTimeout(load, 3000)
    } catch (e) {
      setMessage(`Error: ${e.message}`)
    } finally {
      setRunning(false)
    }
  }

  const triggerReport = async () => {
    setRunning(true)
    setMessage(null)
    try {
      const r = await api.triggerReport(pilotTeam || null)
      setMessage(`Weekly report triggered: ${r.message || 'running in background'}`)
    } catch (e) {
      setMessage(`Error: ${e.message}`)
    } finally {
      setRunning(false)
    }
  }

  const items = metrics?.top_backlog_items || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Process Backlog</h2>
          <p style={{ color: 'var(--muted)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
            Top 5 by score shown. Score = Impact weight × Inverse-effort weight (max 9).
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            value={pilotTeam}
            onChange={e => setPilotTeam(e.target.value)}
            placeholder="Pilot team (optional)"
            style={{ width: 180 }}
          />
          <button onClick={triggerDiscovery} disabled={running}>
            {running ? <span className="spin">⟳</span> : 'Run Discovery'}
          </button>
          <button onClick={triggerReport} disabled={running}>
            Weekly Report
          </button>
          <button onClick={load}>Refresh</button>
        </div>
      </div>

      {message && <p style={{ color: 'var(--green)', fontSize: '0.84rem' }}>{message}</p>}

      {loading ? (
        <p style={{ color: 'var(--muted)' }}><span className="spin">⟳</span> Loading…</p>
      ) : items.length === 0 ? (
        <div className="card">
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
            No backlog items yet. Run Process Discovery to analyse current workflow data.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {items.map((item, i) => (
            <div key={item.finding_id} className="card" style={{ borderLeft: `3px solid ${scoreBorderColor(item.score)}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: 'var(--muted)', fontSize: '1rem' }}>#{i + 1}</span>
                  <code style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{item.finding_id}</code>
                  <span className={`badge badge-${workflowColor(item.workflow)}`}>{item.workflow}</span>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <ScorePill score={item.score} />
                  <EffortBadge effort={item.effort} />
                  <ImpactBadge impact={item.impact} />
                  <span className={`badge badge-${statusColor(item.status)}`}>{item.status}</span>
                </div>
              </div>
              <p style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{item.bottleneck}</p>
              {item.recommended_action && (
                <p style={{ fontSize: '0.83rem', color: 'var(--muted)' }}>
                  <strong style={{ color: 'var(--text)' }}>Action:</strong> {item.recommended_action}
                </p>
              )}
              <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: '0.35rem' }}>
                Discovered {item.discovered_date}
              </p>
            </div>
          ))}
        </div>
      )}

      {metrics && (
        <div className="card">
          <h3 style={{ marginBottom: '0.5rem' }}>Pilot Breakdown</h3>
          {metrics.pilot_breakdown?.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Team</th><th>Stage</th><th>Requests</th>
                  <th>Routing Accuracy</th><th>Satisfaction</th>
                </tr>
              </thead>
              <tbody>
                {metrics.pilot_breakdown.map(p => (
                  <tr key={p.pilot_team}>
                    <td>{p.pilot_team}</td>
                    <td>{p.stage}</td>
                    <td>{p.requests_processed}</td>
                    <td>{(p.routing_accuracy * 100).toFixed(1)}%</td>
                    <td>{p.stakeholder_satisfaction?.toFixed(1)}/5</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>No active pilots</p>}
        </div>
      )}
    </div>
  )
}

const scoreBorderColor = s => s >= 7 ? 'var(--red)' : s >= 5 ? 'var(--yellow)' : 'var(--muted)'
const workflowColor = w => ({ sourcing: 'blue', approval: 'accent', onboarding: 'green', payment: 'yellow' }[w] || 'muted')
const statusColor = s => ({ backlog: 'muted', 'in-experiment': 'blue', shipped: 'green', deprioritized: 'yellow' }[s] || 'muted')

function ScorePill({ score }) {
  const color = score >= 7 ? 'var(--red)' : score >= 5 ? 'var(--yellow)' : 'var(--muted)'
  return (
    <span style={{ fontWeight: 700, fontSize: '1rem', color }}>
      {score}<span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>/9</span>
    </span>
  )
}
function EffortBadge({ effort }) {
  const c = { low: 'badge-green', medium: 'badge-yellow', high: 'badge-red' }[effort] || 'badge-muted'
  return <span className={`badge ${c}`}>effort:{effort}</span>
}
function ImpactBadge({ impact }) {
  const c = { high: 'badge-red', medium: 'badge-yellow', low: 'badge-muted' }[impact] || 'badge-muted'
  return <span className={`badge ${c}`}>impact:{impact}</span>
}
