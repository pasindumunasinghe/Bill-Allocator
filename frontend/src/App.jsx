import React from 'react'
import { api } from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import Upload from './pages/Upload.jsx'
import History from './pages/History.jsx'
import Summary from './pages/Summary.jsx'
import Failed from './pages/Failed.jsx'
import Reports from './pages/Reports.jsx'

const NAV = [
  ['dashboard', 'Dashboard', '▦'],
  ['upload', 'Upload Bills', '⇪'],
  ['history', 'Processing History', '⟲'],
  ['summary', 'Bill Summary', '≣'],
  ['failed', 'Failed Records', '⚠'],
  ['reports', 'Download Reports', '⤓'],
]

function load(key) { try { return localStorage.getItem(key) } catch { return null } }
function save(key, v) { try { v ? localStorage.setItem(key, v) : localStorage.removeItem(key) } catch { /* ignore */ } }

export default function App() {
  const [page, setPage] = React.useState(() => location.hash.slice(1) || 'dashboard')
  const [navOpen, setNavOpen] = React.useState(false)
  const [batch, setBatch] = React.useState(null)
  const [error, setError] = React.useState('')
  const [health, setHealth] = React.useState(null)

  React.useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'down' }))
    const id = load('batchId')
    if (id) api.getBatch(id).then(setBatch).catch(() => save('batchId', null))
  }, [])
  React.useEffect(() => { location.hash = page }, [page])
  React.useEffect(() => {
    const onHash = () => setPage(location.hash.slice(1) || 'dashboard')
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const ctx = {
    batch,
    setBatch: b => { setBatch(b); save('batchId', b?.id) },
    refresh: async () => { if (batch) setBatch(await api.getBatch(batch.id)) },
    newBatch: async () => { const b = await api.createBatch(); setBatch(b); save('batchId', b.id); return b },
    openBatch: async id => { const b = await api.getBatch(id); setBatch(b); save('batchId', id); setPage('dashboard') },
    setError,
    go: setPage,
    health,
  }
  const Page = { dashboard: Dashboard, upload: Upload, history: History, summary: Summary, failed: Failed, reports: Reports }[page] || Dashboard

  return (
    <div className="shell">
      <aside className={`sidebar ${navOpen ? 'open' : ''}`}>
        <div className="brand"><span className="logo">TB</span><div><strong>Telecom Bills</strong><small>Processing System</small></div></div>
        <nav>
          {NAV.map(([key, label, icon]) => (
            <button key={key} className={`nav ${page === key ? 'active' : ''}`} onClick={() => { setPage(key); setNavOpen(false) }}>
              <span className="nav-icon" aria-hidden>{icon}</span>{label}
              {key === 'failed' && batch?.summary.failed > 0 && <span className="pill">{batch.summary.failed}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div>API: <b className={health?.status === 'ok' ? 'txt-ok' : 'txt-bad'}>{health?.status === 'ok' ? 'Online' : health ? 'Offline' : '…'}</b></div>
          {health?.status === 'ok' && <div>OCR: <b className={health.ocr_available ? 'txt-ok' : 'txt-warn'}>{health.ocr_available ? 'Available' : 'Not installed'}</b></div>}
        </div>
      </aside>
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}
      <main className="main">
        <header className="topbar">
          <button className="hamburger" onClick={() => setNavOpen(true)} aria-label="Open menu">☰</button>
          <h1>{NAV.find(n => n[0] === page)?.[1]}</h1>
          <div className="batch-chip">{batch ? <>Current batch <code>{batch.id.slice(0, 8)}</code></> : 'No batch selected'}</div>
        </header>
        {error && <div className="alert" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></div>}
        <Page {...ctx} />
      </main>
    </div>
  )
}
