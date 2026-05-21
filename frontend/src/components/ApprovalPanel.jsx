import { useState } from 'react'
import { api } from '../api.js'

const CATEGORIES = [
  'MRO', 'IT Hardware', 'Electronic Components', 'IT Services',
  'Raw Materials', 'Mechanical Components', 'Logistics', 'Software Licensing',
]

export default function ApprovalPanel() {
  const [form, setForm] = useState({
    requester: '', supplier_name: '', category: 'MRO',
    value: '', currency: 'USD', description: '', pilot_team: '',
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lookupId, setLookupId] = useState('')
  const [lookupResult, setLookupResult] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.submitRequest({
        requester: form.requester,
        supplier_name: form.supplier_name || null,
        category: form.category,
        value: parseFloat(form.value),
        currency: form.currency,
        description: form.description || null,
        pilot_team: form.pilot_team || null,
      })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleLookup = async (e) => {
    e.preventDefault()
    try {
      const res = await api.getRequest(lookupId)
      setLookupResult(res)
    } catch (err) {
      setLookupResult({ error: err.message })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h2>Approval Routing — Policy-Driven</h2>
      <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
        Routing derives strictly from the policy rule table. No inferred authority.
        Policy gaps are flagged and routed to the procurement policy owner.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Submit request */}
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>Submit Purchase Request</h3>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <FieldRow label="Requester">
              <input value={form.requester} onChange={e => setForm(f => ({ ...f, requester: e.target.value }))} placeholder="Name or team" required />
            </FieldRow>
            <FieldRow label="Supplier (optional)">
              <input value={form.supplier_name} onChange={e => setForm(f => ({ ...f, supplier_name: e.target.value }))} placeholder="Supplier name" />
            </FieldRow>
            <FieldRow label="Category">
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                {CATEGORIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </FieldRow>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.5rem' }}>
              <FieldRow label="Value">
                <input value={form.value} onChange={e => setForm(f => ({ ...f, value: e.target.value }))} placeholder="50000" type="number" required />
              </FieldRow>
              <FieldRow label="Currency">
                <select value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}>
                  {['USD', 'INR', 'EUR', 'GBP'].map(c => <option key={c}>{c}</option>)}
                </select>
              </FieldRow>
            </div>
            <FieldRow label="Description">
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Optional" />
            </FieldRow>
            <FieldRow label="Pilot Team">
              <input value={form.pilot_team} onChange={e => setForm(f => ({ ...f, pilot_team: e.target.value }))} placeholder="e.g. pilot-alpha" />
            </FieldRow>
            <button type="submit" disabled={loading} style={{ marginTop: '0.25rem' }}>
              {loading ? <span className="spin">⟳</span> : 'Submit & Route'}
            </button>
          </form>
          {error && <p className="err">Error: {error}</p>}
        </div>

        {/* Result */}
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>Routing Result</h3>
          {result ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <code style={{ fontSize: '0.9rem' }}>{result.request_id}</code>
                <span className={`badge badge-${result.status === 'pending' ? 'blue' : 'green'}`}>{result.status}</span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
                Routing triggered in background — check status below.
              </p>
              <button onClick={() => setLookupId(result.request_id)} style={{ fontSize: '0.78rem' }}>
                Load Status for {result.request_id}
              </button>
            </div>
          ) : (
            <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>Submit a request to see routing output.</p>
          )}
        </div>
      </div>

      {/* Status lookup */}
      <div className="card">
        <h3 style={{ marginBottom: '0.75rem' }}>Request Status Lookup</h3>
        <form onSubmit={handleLookup} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <input value={lookupId} onChange={e => setLookupId(e.target.value)} placeholder="PR-XXXXXXXX" style={{ flex: 1 }} />
          <button type="submit">Lookup</button>
        </form>
        {lookupResult && !lookupResult.error && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem' }}>
            <Row label="Request ID" value={<code>{lookupResult.request_id}</code>} />
            <Row label="Status" value={<span className={`badge badge-${lookupResult.status === 'pending' ? 'blue' : 'green'}`}>{lookupResult.status}</span>} />
            <Row label="Requester" value={lookupResult.requester} />
            <Row label="Category" value={lookupResult.category} />
            <Row label="Value" value={`${lookupResult.currency} ${Number(lookupResult.value).toLocaleString()}`} />
            {lookupResult.approval_decision && (
              <>
                <hr style={{ borderColor: 'var(--border)' }} />
                <h3 style={{ marginBottom: '0.25rem' }}>Approval Decision</h3>
                <Row label="Policy Rule" value={lookupResult.approval_decision.policy_rule_id} />
                <Row label="Approval Chain" value={lookupResult.approval_decision.approval_chain?.join(' → ')} />
                <Row label="SLA" value={`${lookupResult.approval_decision.sla_hours}h`} />
                {lookupResult.approval_decision.is_policy_gap && (
                  <span className="badge badge-red">POLICY GAP</span>
                )}
              </>
            )}
            {lookupResult.supplier_score && (
              <>
                <hr style={{ borderColor: 'var(--border)' }} />
                <h3 style={{ marginBottom: '0.25rem' }}>Supplier Score</h3>
                <Row label="Composite" value={lookupResult.supplier_score.composite?.toFixed(2)} />
                <Row label="Status" value={lookupResult.supplier_score.status} />
              </>
            )}
          </div>
        )}
        {lookupResult?.error && <p className="err">{lookupResult.error}</p>}
      </div>
    </div>
  )
}

function FieldRow({ label, children }) {
  return (
    <div>
      <label style={{ fontSize: '0.78rem', color: 'var(--muted)', display: 'block', marginBottom: 2 }}>{label}</label>
      {children}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span style={{ textAlign: 'right' }}>{value}</span>
    </div>
  )
}
