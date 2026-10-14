import React from 'react'
import { STATUS } from '../format.js'
import { api } from '../api.js'

const tone = {
  [STATUS.OK]: 'ok', [STATUS.QUEUED]: 'neutral', [STATUS.PROCESSING]: 'info',
  [STATUS.READ]: 'bad', [STATUS.INVALID]: 'bad', [STATUS.UNSUPPORTED]: 'bad',
  [STATUS.REVIEW]: 'warn', [STATUS.USAGE]: 'info', [STATUS.IGNORED]: 'muted',
}

export function StatusBadge({ status }) {
  return <span className={`badge badge-${tone[status] || 'neutral'}`}>{status}</span>
}

export function GroupBadge({ group }) {
  if (!group) return <span className="dim">—</span>
  return <span className={`group group-${group.toLowerCase()}`}>Group {group}</span>
}

export function Card({ label, value, sub, accent }) {
  return (
    <div className={`card stat ${accent ? 'stat-' + accent : ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

export function Panel({ title, actions, children }) {
  return (
    <section className="card panel">
      {(title || actions) && (
        <header className="panel-head">
          <h2>{title}</h2>
          <div className="panel-actions">{actions}</div>
        </header>
      )}
      {children}
    </section>
  )
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function Filters({ search, setSearch, status, setStatus, group, setGroup, statuses }) {
  return (
    <div className="filters">
      <input className="input" placeholder="Search file, contract, subscription…" value={search}
        onChange={e => setSearch(e.target.value)} aria-label="Search" />
      {setStatus && (
        <select className="input" value={status} onChange={e => setStatus(e.target.value)} aria-label="Status filter">
          <option value="">All statuses</option>
          {statuses.map(s => <option key={s}>{s}</option>)}
        </select>
      )}
      {setGroup && (
        <select className="input" value={group} onChange={e => setGroup(e.target.value)} aria-label="Group filter">
          <option value="">All groups</option>
          <option value="A">Group A</option>
          <option value="B">Group B</option>
          <option value="none">Unclassified</option>
        </select>
      )}
    </div>
  )
}

export function useFilter(files) {
  const [search, setSearch] = React.useState('')
  const [status, setStatus] = React.useState('')
  const [group, setGroup] = React.useState('')
  const q = search.trim().toLowerCase()
  const rows = files.filter(f =>
    (!q || [f.file_name, f.contract_number, f.subscription_number, f.bill_month].some(v => v && v.toLowerCase().includes(q))) &&
    (!status || f.status === status) &&
    (!group || (group === 'none' ? !f.group : f.group === group)))
  return { rows, props: { search, setSearch, status, setStatus, group, setGroup, statuses: Object.values(STATUS) } }
}

function TextViewer({ file }) {
  const [data, setData] = React.useState(null)
  if (!file.extraction_method) return null
  return (
    <>
      <button className="link sm" onClick={() => api.fileText(file.id).then(setData).catch(e => setData({ text: e.message }))}>View extracted text</button>
      {data && (
        <div className="modal-scrim" onClick={() => setData(null)}>
          <div className="modal card" onClick={e => e.stopPropagation()}>
            <header className="panel-head"><h2>{file.file_name} — text read by the app ({data.method})</h2>
              <button className="btn sm" onClick={() => navigator.clipboard?.writeText(data.text)}>Copy</button>
              <button className="btn sm" onClick={() => setData(null)}>Close</button></header>
            <pre className="extracted">{data.text || '(no text)'}</pre>
          </div>
        </div>
      )}
    </>
  )
}

export function ErrorList({ file }) {
  const items = [...(file.errors || [])]
  if (!items.length && !file.notes?.length) return <span className="dim">—</span>
  return (
    <div className="errs">
      {file.status !== STATUS.OK && <TextViewer file={file} />}
      {items.map((e, i) => <div key={i} className="err">{e}</div>)}
      {(file.notes || []).map((n, i) => <div key={'n' + i} className="note">{n}</div>)}
    </div>
  )
}
