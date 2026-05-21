import { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function PilotPanel() {
  const [pilots, setPilots] = useState([])
  const [selected, setSelected] = useState(null)
  const [feedback, setFeedback] = useState([])
  const [loading, setLoading] = useState(true)
  const [fbForm, setFbForm] = useState({ rating: 4, feedback_text: '', submitted_by: '' })
  const [message, setMessage] = useState(null)

  const loadPilots = async () => {
    setLoading(true)
    try {
      const p = await api.getPilots()
      setPilots(p)
      if (p.length > 0 && !selected) setSelected(p[0].pilot_team)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadPilots() }, [])

  useEffect(() => {
    if (!selected) return
    api.getPilotFeedback(selected).then(setFeedback).catch(() => setFeedback([]))
  }, [selected])

  const submitFeedback = async (e) => {
    e.preventDefault()
    if (!selected) return
    try {
      await api.submitFeedback(selected, fbForm)
      setMessage('Feedback submitted')
      setFbForm({ rating: 4, feedback_text: '', submitted_by: '' })
      const f = await api.getPilotFeedback(selected)
      setFeedback(f)
    } catch (err) {
      setMessage(`Error: ${err.message}`)
    }
  }

  const activePilot = pilots.find(p => p.pilot_team === selected)

  if (loading) return <p style={{ color: 'var(--muted)' }}><span className="spin">⟳</span> Loading…</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h2>Pilot Deployment Status</h2>

      {pilots.length === 0 ? (
        <div className="card">
          <p style={{ color: 'var(--muted)' }}>No pilots seeded yet. Add pilot_teams.json to data/seed/ and restart.</p>
        </div>
      ) : (
        <>
          {/* Pilot selector */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {pilots.map(p => (
              <button
                key={p.pilot_team}
                onClick={() => setSelected(p.pilot_team)}
                style={{
                  borderColor: selected === p.pilot_team ? 'var(--accent)' : 'var(--border)',
                  background: selected === p.pilot_team ? 'var(--accent-dim)' : 'transparent',
                }}
              >
                {p.pilot_team}
                <span style={{ marginLeft: '0.4rem' }}>
                  <span className={`badge badge-${p.status === 'active' ? 'green' : 'muted'}`}>{p.status}</span>
                </span>
              </button>
            ))}
          </div>

          {activePilot && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              {/* Pilot metrics */}
              <div className="card">
                <h3 style={{ marginBottom: '0.75rem' }}>Pilot Metrics — {activePilot.pilot_team}</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.87rem' }}>
                  <Row label="Stage" value={activePilot.stage} />
                  <Row label="Active Users" value={activePilot.active_users} />
                  <Row label="Requests Processed" value={activePilot.requests_processed} />
                  <Row label="Routing Accuracy" value={`${(activePilot.routing_accuracy * 100).toFixed(1)}%`} />
                  <Row label="Avg Scoring Confidence" value={`${(activePilot.avg_scoring_confidence * 100).toFixed(0)}%`} />
                  <Row label="Stakeholder Satisfaction" value={
                    <span>
                      {activePilot.stakeholder_satisfaction?.toFixed(1)}/5
                      <Stars rating={activePilot.stakeholder_satisfaction} />
                    </span>
                  } />
                  <Row label="Open Feedback Items" value={activePilot.open_feedback_items} />
                  <Row label="Prompt Version" value={<code style={{ fontSize: '0.78rem' }}>{activePilot.prompt_version}</code>} />
                  <Row label="Status" value={<span className={`badge badge-${activePilot.status === 'active' ? 'green' : 'muted'}`}>{activePilot.status}</span>} />
                </div>
                {activePilot.blockers?.length > 0 && (
                  <div style={{ marginTop: '0.75rem', padding: '0.6rem', background: '#450a0a', borderRadius: 6 }}>
                    <h3 style={{ color: 'var(--red)', marginBottom: '0.35rem' }}>Blockers</h3>
                    {activePilot.blockers.map((b, i) => <p key={i} style={{ fontSize: '0.83rem' }}>{b}</p>)}
                  </div>
                )}
              </div>

              {/* Feedback */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="card">
                  <h3 style={{ marginBottom: '0.75rem' }}>Submit Feedback</h3>
                  <form onSubmit={submitFeedback} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    <div>
                      <label style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>Rating (1–5)</label>
                      <input type="number" min={1} max={5} value={fbForm.rating}
                        onChange={e => setFbForm(f => ({ ...f, rating: parseInt(e.target.value) }))} />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>Feedback</label>
                      <textarea rows={3} value={fbForm.feedback_text}
                        onChange={e => setFbForm(f => ({ ...f, feedback_text: e.target.value }))}
                        placeholder="What's working or not?" />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>Submitted by</label>
                      <input value={fbForm.submitted_by}
                        onChange={e => setFbForm(f => ({ ...f, submitted_by: e.target.value }))}
                        placeholder="Name or role" />
                    </div>
                    <button type="submit">Submit</button>
                    {message && <p style={{ color: 'var(--green)', fontSize: '0.8rem' }}>{message}</p>}
                  </form>
                </div>

                <div className="card">
                  <h3 style={{ marginBottom: '0.75rem' }}>Recent Feedback</h3>
                  {feedback.length === 0 ? (
                    <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>No feedback yet</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {feedback.slice(0, 6).map(f => (
                        <div key={f.id} style={{ padding: '0.5rem', background: 'var(--bg)', borderRadius: 6 }}>
                          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                            <Stars rating={f.rating} />
                            <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{f.submitted_by}</span>
                          </div>
                          {f.feedback_text && <p style={{ fontSize: '0.83rem' }}>{f.feedback_text}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span>{value}</span>
    </div>
  )
}

function Stars({ rating }) {
  const n = Math.round(rating || 0)
  return (
    <span style={{ color: 'var(--yellow)', fontSize: '0.78rem' }}>
      {'★'.repeat(n)}{'☆'.repeat(5 - n)}
    </span>
  )
}
