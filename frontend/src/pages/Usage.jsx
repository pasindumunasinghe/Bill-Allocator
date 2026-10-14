import React from 'react'
import { api } from '../api.js'
import { Empty, Panel } from '../components/ui.jsx'
import { money } from '../format.js'

const gb = v => (v == null ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 4 }))

function Picker({ label, hint, accept, file, setFile }) {
  const ref = React.useRef()
  return (
    <div className="picker">
      <div><b>{label}</b><div className="dim">{hint}</div></div>
      <div className="picker-files">{file ? <span className="ftype">{file.name}</span> : <span className="dim">No file</span>}</div>
      <input ref={ref} type="file" hidden accept={accept} onChange={e => { setFile(e.target.files[0] || null); e.target.value = '' }} />
      {file && <button className="btn sm ghost" onClick={() => setFile(null)}>Remove</button>}
      <button className="btn sm" onClick={() => ref.current.click()}>Choose</button>
    </div>
  )
}

function BillPreview({ expected, bill }) {
  if (!bill) return null
  const ok = bill.bill_type === expected && !bill.errors?.length
  return (
    <div className={`bill-preview ${ok ? '' : 'bad'}`}>
      <div className="bp-head">
        <b>{expected === 'SLT' ? 'SLT' : 'Dialog'} bill preview</b>
        <span className={`badge ${ok ? 'badge-ok' : 'badge-bad'}`}>{ok ? 'Valid' : 'Check bill'}</span>
      </div>
      {bill.bill_type && bill.bill_type !== expected && <div className="err">This is a {bill.bill_type} bill — upload it in the {bill.bill_type === 'SLT' ? 'SLT' : 'Dialog'} box.</div>}
      {(bill.errors || []).map(e => <div key={e} className="err">{e}</div>)}
      {bill.bill_type && (
        <table className="mini"><tbody>
          <tr><td>{bill.bill_type === 'SLT' ? 'Account Number' : 'Contract Number'}</td><td className="num">{bill.reference}</td></tr>
          <tr><td>Bill Period</td><td className="num">{bill.bill_period || 'Not found'}</td></tr>
          {bill.components.map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{money(v)}</td></tr>)}
          <tr className="strong"><td>Bill Value (to allocate)</td><td className="num">{money(bill.bill_value)}</td></tr>
          <tr><td className="dim">VAT (excluded)</td><td className="num dim">{money(bill.vat)}</td></tr>
        </tbody></table>
      )}
    </div>
  )
}

export function ResultPreview({ r, setError }) {
  const [tab, setTab] = React.useState('bill')
  const p = r.preview
  return (
    <div className="card result">
      <header className="panel-head">
        <h2>{r.bill_type === 'SLT' ? 'SLT' : 'Dialog'} — {r.bill_period || r.bill_file}</h2>
        {r.download && <button className="btn primary sm" onClick={() => api.downloadUrl(r.download, r.file_name).catch(e => setError(e.message))}>Download Excel</button>}
      </header>
      {!p ? <div className="pad-box">{r.errors.map(e => <div key={e} className="err">{e}</div>)}</div> : (
        <>
          <div className="tabs inner">
            {[['bill', 'Bill Summary'], ['company', 'Company Wise'], ['users', `Allocation (${p.users.length})`], ['unmapped', `Unmapped (${p.unmapped.length})`]].map(([k, l]) =>
              <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          <div className="table-wrap">
            {tab === 'bill' && <table><tbody>
              <tr><td>Bill File</td><td>{p.bill.bill_file}</td></tr>
              <tr><td>{p.bill.bill_type === 'SLT' ? 'Account Number' : 'Contract Number'}</td><td>{p.bill.reference}</td></tr>
              <tr><td>Bill Period</td><td>{p.bill.bill_period || '—'}</td></tr>
              {p.bill.components.map(([k, v]) => <tr key={k}><td>{k}</td><td className="num-l">{money(v)}</td></tr>)}
              <tr className="strong"><td>Bill Value</td><td className="num-l">{money(p.bill.bill_value)}</td></tr>
              <tr><td>VAT (excluded)</td><td className="num-l">{money(p.bill.vat)}</td></tr>
              <tr><td>Grand Total Usage (GB)</td><td className="num-l">{gb(p.summary.grand_total_usage)}</td></tr>
              <tr><td>Unit Cost per GB</td><td className="num-l">{p.summary.unit_cost}</td></tr>
              <tr className="strong"><td>Total Allocated</td><td className="num-l">{money(p.summary.allocated)}</td></tr>
              <tr><td>Difference (Bill − Allocated)</td><td className="num-l">{money(p.summary.difference)}</td></tr>
              <tr><td>All Company usage redistributed (GB) / to users</td><td className="num-l">{gb(p.summary.all_company_pool)} / {p.summary.recipients}</td></tr>
              <tr><td>Unmapped usage, not allocated (GB)</td><td className="num-l">{gb(p.summary.unmapped_usage)}</td></tr>
            </tbody></table>}
            {tab === 'company' && <table>
              <thead><tr><th>Company</th><th className="num">Users</th><th className="num">Usage (GB)</th><th className="num">Allocated Cost</th></tr></thead>
              <tbody>{p.companies.map(c => <tr key={c[0]}><td>{c[0]}</td><td className="num">{c[1]}</td><td className="num">{gb(c[2])}</td><td className="num">{money(c[3])}</td></tr>)}
                <tr className="strong"><td>Total</td><td /><td className="num">{gb(p.summary.grand_total_usage)}</td><td className="num">{money(p.summary.allocated)}</td></tr></tbody>
            </table>}
            {tab === 'users' && <table>
              <thead><tr><th>Username</th><th>Emp No</th><th>Emp Name</th><th>Company</th><th>Dimension</th><th className="num">Final Usage (GB)</th><th className="num">Cost</th></tr></thead>
              <tbody>{p.users.map(u => <tr key={u[0]}><td>{u[0]}</td><td>{u[1]}</td><td>{u[2]}</td><td>{u[3]}</td><td><code>{u[4]}</code></td><td className="num">{gb(u[5])}</td><td className="num">{money(u[6])}</td></tr>)}</tbody>
            </table>}
            {tab === 'unmapped' && (p.unmapped.length ? <table>
              <thead><tr><th>Username</th><th className="num">Total Usage (GB)</th><th>Reason</th></tr></thead>
              <tbody>{p.unmapped.map(u => <tr key={u[0]}><td>{u[0]}</td><td className="num">{gb(u[1])}</td><td>User not found in Master data</td></tr>)}</tbody>
            </table> : <Empty>All users matched.</Empty>)}
          </div>
        </>
      )}
    </div>
  )
}

export default function Usage({ setError }) {
  const [slt, setSlt] = React.useState(null)
  const [dialog, setDialog] = React.useState(null)
  const [sltInfo, setSltInfo] = React.useState(null)
  const [dialogInfo, setDialogInfo] = React.useState(null)
  const [usage, setUsage] = React.useState(null)
  const [master, setMaster] = React.useState(null)
  const [map, setMap] = React.useState(null)
  const [save, setSave] = React.useState(true)
  const [ref, setRef] = React.useState({})
  const [busy, setBusy] = React.useState(false)
  const [result, setResult] = React.useState(null)
  React.useEffect(() => { api.usageReference().then(setRef).catch(() => {}) }, [result])

  const pickBill = (setFile, setInfo) => async file => {
    setFile(file); setInfo(null); setResult(null)
    if (file) setInfo(await api.previewBill(file).catch(e => ({ errors: [e.message], components: [] })))
  }
  const bills = [slt, dialog].filter(Boolean)
  const wrongBox = (sltInfo && sltInfo.bill_type && sltInfo.bill_type !== 'SLT') || (dialogInfo && dialogInfo.bill_type && dialogInfo.bill_type !== 'DIALOG')

  const run = async () => {
    setBusy(true); setError(''); setResult(null)
    try { setResult(await api.usageAllocate(bills, usage, master, map, save)) } catch (e) { setError(e.message) }
    setBusy(false)
  }

  return (
    <>
      <p className="caption">Split the SLT (account 003 311 8626) and Dialog (contract B698359) bills across employees by data usage. Upload one or both bills; each gives its own Excel file.</p>
      <div className="grid two">
        <Panel title="SLT bill">
          <Picker label="SLT bill PDF" hint="Account 003 311 8626" accept=".pdf" file={slt} setFile={pickBill(setSlt, setSltInfo)} />
          <BillPreview expected="SLT" bill={sltInfo} />
        </Panel>
        <Panel title="Dialog bill">
          <Picker label="Dialog bill PDF" hint="Contract B698359" accept=".pdf" file={dialog} setFile={pickBill(setDialog, setDialogInfo)} />
          <BillPreview expected="DIALOG" bill={dialogInfo} />
        </Panel>
      </div>
      <Panel title="Usage and employee data">
        <div className="pickers">
          <Picker label="Usage Excel" hint="Sheets with 'Source User' or 'username' + usage columns" accept=".xlsx" file={usage} setFile={setUsage} />
          <Picker label="Master data (Emp.xlsx)" hint={ref.master ? `Optional — saved default: ${ref.master}` : 'Required (no saved default yet)'} accept=".xlsx" file={master} setFile={setMaster} />
          <Picker label="map.xlsx" hint={ref.map ? `Optional — saved default: ${ref.map}` : 'Optional'} accept=".xlsx" file={map} setFile={setMap} />
        </div>
        <div className="toolbar pad">
          <label className="dim"><input type="checkbox" checked={save} onChange={e => setSave(e.target.checked)} /> Save uploaded Master / map as defaults</label>
          <span className="spacer" />
          <button className="btn primary" disabled={busy || !bills.length || wrongBox || !usage || (!master && !ref.master)} onClick={run}>
            {busy ? 'Processing…' : `Allocate ${bills.length === 2 ? 'both bills' : 'bill'}`}
          </button>
        </div>
      </Panel>
      {result && (
        <>
          {result.warnings.map(w => <div key={w} className="alert warn">{w}</div>)}
          <div className="grid results">{result.results.map(r => <ResultPreview key={r.bill_file} r={r} setError={setError} />)}</div>
        </>
      )}
    </>
  )
}
