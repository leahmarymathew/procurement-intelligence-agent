import { useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import SupplierPanel from './components/SupplierPanel.jsx'
import ApprovalPanel from './components/ApprovalPanel.jsx'
import ProcessBacklog from './components/ProcessBacklog.jsx'
import PilotPanel from './components/PilotPanel.jsx'

const TABS = [
  { id: 'dashboard',  label: 'Dashboard' },
  { id: 'supplier',   label: 'Supplier Scoring' },
  { id: 'approval',   label: 'Approval Routing' },
  { id: 'backlog',    label: 'Process Backlog' },
  { id: 'pilot',      label: 'Pilot Status' },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 1.5rem' }}>
      <header style={{
        display: 'flex', alignItems: 'center', gap: '1.5rem',
        padding: '1rem 0', borderBottom: '1px solid var(--border)', marginBottom: '1.5rem'
      }}>
        <div>
          <h1 style={{ letterSpacing: '-0.02em' }}>S2P Procurement Intelligence</h1>
          <span className="tag">procurement-agent-v1.0</span>
        </div>
        <nav style={{ display: 'flex', gap: '0.25rem', marginLeft: 'auto' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                border: tab === t.id ? '1px solid var(--accent)' : '1px solid var(--border)',
                background: tab === t.id ? 'var(--accent-dim)' : 'transparent',
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main style={{ paddingBottom: '3rem' }}>
        {tab === 'dashboard' && <Dashboard />}
        {tab === 'supplier'  && <SupplierPanel />}
        {tab === 'approval'  && <ApprovalPanel />}
        {tab === 'backlog'   && <ProcessBacklog />}
        {tab === 'pilot'     && <PilotPanel />}
      </main>
    </div>
  )
}
