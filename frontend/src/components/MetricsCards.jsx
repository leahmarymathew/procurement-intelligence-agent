export default function MetricsCards({ metrics }) {
  const cards = [
    { label: 'Requests Processed',   value: metrics.requests_processed,      color: 'var(--blue)' },
    { label: 'Supplier Scores',       value: metrics.supplier_scores_generated, color: 'var(--accent)' },
    { label: 'Approval Decisions',    value: metrics.approval_decisions_made,  color: 'var(--green)' },
    { label: 'Avg Cycle (hrs)',        value: metrics.avg_approval_cycle_hours.toFixed(1), color: 'var(--muted)' },
    { label: 'Escalation Rate',        value: `${(metrics.escalation_rate * 100).toFixed(1)}%`, color: metrics.escalation_rate > 0.15 ? 'var(--red)' : 'var(--green)' },
    { label: 'Policy Gaps',            value: metrics.policy_gap_count,         color: metrics.policy_gap_count > 0 ? 'var(--yellow)' : 'var(--muted)' },
    { label: 'Process Findings',       value: metrics.process_findings_count,   color: 'var(--accent)' },
    { label: 'Avg Confidence',         value: `${(metrics.avg_confidence * 100).toFixed(0)}%`, color: 'var(--green)' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem' }}>
      {cards.map(c => (
        <div key={c.label} className="card" style={{ padding: '1rem' }}>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: c.color, lineHeight: 1 }}>
            {c.value}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '0.4rem' }}>
            {c.label}
          </div>
        </div>
      ))}
    </div>
  )
}
