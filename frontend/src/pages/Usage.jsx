import React from 'react'
import { api } from '../api.js'
import { Empty, Panel } from '../components/ui.jsx'
import { money } from '../format.js'

function Picker({ label, hint, accept, multiple, files, setFiles }) {
  const ref = React.useRef()
  const list = files ? (Array.isArray(files) ? files : [files]) : []
  return (
    <div className="picker">
      <div><b>{label}</b><div className="dim">{hint}</div></div>
      <div className="picker-files">{list.length ? list.map(f => <span key={f.name} className="ftype">{f.name}</span>) : <span className="dim">No file</span>}</div>
      <input ref={ref} type="file" hidden accept={accept} multiple={multiple}
        onChange={e => { const fl = Array.from(e.target.files); setFiles(multiple ? fl : fl[0] || null); e.target.value = '' }} />
      <button className="btn sm" onClick={() => ref.current.click()}>Choose</button>
    </div>
  )
}

export default function Usage({ setError }) {
  const [bills, setBills] = React.useState([])
  const [usage, setUsage] = React.useState(null)
  const [master, setMaster] = React.useState(null)
  const [map, setMap] = React.useState(null)
  const [save, setSave] = React.useState(true)
  const [ref, setRef] = React.useState({})
  const [busy, setBusy] = React.useState(false)
  const [result, setResult] = React.useState(null)
  React.useEffect(() => { api.usageReference().then(setRef).catch(() => {}) }, [result])

  const tooMany = bills.length > 2
  const run = async () => {
    setBusy(true); setError(''); setResult(null)
    try {
      const r = await api.usageAllocate(bills, usage, master, map, save)
      setResult(r)
      for (const x of r.results) if (x.download) await api.downloadUrl(x.download, x.file_name)
    } catch (e) { setError(e.message) }
    setBusy(false)
  }

  return (
    <>
      <p className="caption">Allocates the Dialog (contract B698359) and SLT (account 003 311 8626) bills to employees by data usage. Each bill produces its own Excel file.</p>
      <Panel title="Input files">
        <div className="pickers">
          <Picker label="Bill PDFs (max 2)" hint="Dialog B698359 and/or SLT 003 311 8626" accept=".pdf" multiple files={bills} setFiles={setBills} />
          <Picker label="Usage Excel" hint="Sheets with 'Source User' or 'username' + usage columns" accept=".xlsx" files={usage} setFiles={setUsage} />
          <Picker label="Master data (Emp.xlsx)" hint={ref.master ? `Optional — saved default: ${ref.master}` : 'Required (no saved default yet)'} accept=".xlsx" files={master} setFiles={setMaster} />
          <Picker label="map.xlsx" hint={ref.map ? `Optional — saved default: ${ref.map}` : 'Optional'} accept=".xlsx" files={map} setFiles={setMap} />
        </div>
        <div className="toolbar pad">
          <label className="dim"><input type="checkbox" checked={save} onChange={e => setSave(e.target.checked)} /> Save uploaded Master / map as defaults</label>
          <span className="spacer" />
          {tooMany && <span className="err">Only maximum 2 bills allowed</span>}
          <button className="btn primary" disabled={busy || !bills.length || tooMany || !usage || (!master && !ref.master)} onClick={run}>
            {busy ? 'Processing…' : 'Allocate & Download'}
          </button>
        </div>
      </Panel>
      <Panel title="Results">
        {!result ? <Empty>Choose the files above and click Allocate & Download.</Empty> : (
          <>
            {result.warnings.map(w => <div key={w} className="alert warn">{w}</div>)}
            <div className="table-wrap"><table>
              <thead><tr><th>Bill</th><th>Type</th><th>Period</th><th className="num">Bill Value</th><th className="num">Allocated</th><th className="num">Users (mapped / unmapped)</th><th>Status</th><th /></tr></thead>
              <tbody>{result.results.map(x => (
                <tr key={x.bill_file}>
                  <td className="file">{x.bill_file}</td><td>{x.bill_type || '—'}</td><td>{x.bill_period || '—'}</td>
                  <td className="num">{money(x.bill_value)}</td><td className="num">{money(x.allocated)}</td>
                  <td className="num">{x.mapped_users != null ? `${x.mapped_users} / ${x.unmapped_users}` : '—'}</td>
                  <td>{x.status === 'Processed Successfully' ? <span className="badge badge-ok">{x.status}</span> : <><span className="badge badge-bad">{x.status}</span>{x.errors.map(e => <div key={e} className="err">{e}</div>)}</>}</td>
                  <td>{x.download && <button className="btn sm" onClick={() => api.downloadUrl(x.download, x.file_name).catch(e => setError(e.message))}>Download</button>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          </>
        )}
      </Panel>
    </>
  )
}
