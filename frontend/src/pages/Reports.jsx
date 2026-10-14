import React from 'react'
import { api } from '../api.js'
import { Empty, Panel } from '../components/ui.jsx'
import { STATUS } from '../format.js'

export default function Reports({ batch, setError, go }) {
  const [info, setInfo] = React.useState(null)
  React.useEffect(() => { if (batch) api.reports(batch.id).then(setInfo).catch(e => setError(e.message)) }, [batch])
  if (!batch) return <Panel title="Download Reports"><Empty>No batch selected.</Empty></Panel>
  const pending = batch.files.some(f => f.status === STATUS.QUEUED || f.status === STATUS.PROCESSING)

  const card = (key, g, title, sheets) => {
    const r = info?.[key]
    return (
      <div className="card report">
        <div className="report-icon">XLSX</div>
        <h3>{r?.file_name || '…'}</h3>
        <p className="dim">{title}</p>
        <ul>{sheets.map(s => <li key={s}>{s}</li>)}</ul>
        <p>{r ? <><b>{r.processed}</b> processed of <b>{r.records}</b> Group {g.toUpperCase()} record(s)</> : 'Loading…'}</p>
        <button className="btn primary" disabled={!r?.available || pending}
          onClick={() => api.download(batch.id, g).catch(e => setError(e.message))}>Download</button>
        {r && !r.available && <p className="dim">No Group {g.toUpperCase()} bills in this batch.</p>}
      </div>
    )
  }
  return (
    <>
      {pending && <div className="alert warn">Some files are still queued. <button className="link" onClick={() => go('upload')}>Process them</button> before exporting.</div>}
      <p className="caption">Group A and Group B are always exported to separate workbooks and are never merged.</p>
      <div className="grid reports">
        {card('group_a', 'a', 'Group A · contract 74745984 · split equally across 4 companies', ['Allocation Summary', 'Calculation Summary', 'Validation'])}
        {card('group_b', 'b', 'Group B · fixed company & cost center mapping', ['Bill Summary', 'Cost Center Summary', 'Failed Records'])}
      </div>
      <div className="card report" style={{ marginTop: 18 }}>
        <div className="report-icon">XLSX</div>
        <h3>Final_Report_WiFi_&lt;MONTH&gt;.xlsx</h3>
        <p className="dim">Cumulative monthly report across all batches: one sheet per contract with a block per bill month, plus a Company Summary by month.</p>
        <button className="btn primary" disabled={pending} onClick={() => api.downloadFinal().catch(e => setError(e.message))}>Download Final Report</button>
      </div>
    </>
  )
}
