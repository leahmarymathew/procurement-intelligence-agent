// In dev: Vite proxies /api → http://localhost:8000 (see vite.config.js)
// In production: set VITE_API_BASE_URL to the backend origin (e.g. https://your-api.onrender.com)
const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  health:          ()       => req('/health'),
  getMetrics:      (date)   => req(`/metrics${date ? `?metric_date=${date}` : ''}`),
  getMetricsHistory: (days) => req(`/metrics/history?days=${days || 7}`),
  getAuditLog:     (limit)  => req(`/audit-log?limit=${limit || 50}`),
  getAuditSummary: ()       => req('/metrics/audit-summary'),
  getPilots:       ()       => req('/pilot'),
  getPilot:        (team)   => req(`/pilot/${team}/summary`),
  getPilotFeedback:(team)   => req(`/pilot/${team}/feedback`),
  submitFeedback:  (team, body) => req(`/pilot/${team}/feedback`, { method: 'POST', body: JSON.stringify(body) }),
  submitRequest:   (body)   => req('/procurement/request', { method: 'POST', body: JSON.stringify(body) }),
  getRequest:      (id)     => req(`/procurement/request/${id}`),
  scoreSupplier:   (body)   => req('/procurement/supplier/score', { method: 'POST', body: JSON.stringify(body) }),
  triggerDiscovery:(team)   => req(`/procurement/process-discovery${team ? `?pilot_team=${team}` : ''}`, { method: 'POST' }),
  triggerReport:   (team)   => req(`/procurement/weekly-report${team ? `?pilot_team=${team}` : ''}`, { method: 'POST' }),
}
