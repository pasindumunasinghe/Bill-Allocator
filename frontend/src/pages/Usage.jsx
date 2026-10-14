import React from 'react'
import { api } from '../api.js'
import { Empty, Panel } from '../components/ui.jsx'
import { dateTime, money } from '../format.js'

const gb = v => (v == null ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 4 }))

function StoredFile({ kind, label, hint, accept, meta, busy, onUpload, onRemove, error, children }) {
  const ref = React.useRef()
  return (
    <div className="stored">
      <div className="picker">
        <div><b>{label}</b><div className="dim">{hint}</div></div>
        <div className="picker-files">
          {busy ? <span className="badge badge-info">Uploading…</span>
            : meta ? <span className="badge badge-ok" title={meta.stored_at || ''}>✓ Stored{meta.stored_at ? ` · ${dateTime(meta.stored_at)}` : ''}</span>
              : <span className="dim">Not uploaded</span>}
        </div>
        <input ref={ref} type="file" hidden accept={accept} onChange={e => { const f = e.target.files[0]; e.target.value = ''; if (f) onUpload(kind, f) }} />
        {meta && <button className="btn sm ghost" disabled={busy} onClick={() => onRemove(kind)}>Remove</button>}
        <button className="btn sm" disabled={busy} onClick={() => ref.current.click()}>{meta ? 'Replace' : 'Upload'}</button>
      </div>
      {error && <div className="pad-box err">Not stored: {error}</div>}
      {meta && <div className="stored-name"><span className="ftype">{meta.file_name}</span></div>}
      {meta?.preview && children(meta.preview)}
    </div>
  )
}

function BillPreview({ bill }) {
  return (
    <table className="mini preview"><tbody>
      <tr><td>{bill.bill_type === 'SLT' ? 'Account Number' : 'Contract Number'}</td><td className="num">{bill.reference}</td></tr>
      <tr><td>Bill Period</td><td className="num">{bill.bill_period || 'Not found'}</td></tr>
      {bill.components.map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{money(v)}</td></tr>)}
      <tr className="strong"><td>Bill Value (to allocate)</td><td className="num">{money(bill.bill_value)}</td></tr>
      <tr><td className="dim">VAT (excluded)</td><td className="num dim">{money(bill.vat)}</td></tr>
      {(bill.errors || []).map(e => <tr key={e}><td colSpan={2} className="err">{e}</td></tr>)}
    </tbody></table>
  )
}

function UsagePreview({ p }) {
  return (
    <div className="preview">
      <div className="dim">{p.users} users · {gb(p.total_gb)} GB total</div>
      <div className="table-wrap"><table className="mini">
        <thead><tr><th>Sheet</th><th>Type</th><th>Usage column</th><th className="num">Users</th><th className="num">GB</th><th className="num">Excluded / duplicates</th></tr></thead>
        <tbody>{p.sheets.map(s => <tr key={s.name}><td>{s.name}</td><td>{s.type}</td><td>{s.usage_col} ({s.unit})</td><td className="num">{s.users}</td><td className="num">{gb(s.total_gb)}</td><td className="num">{s.excluded_rows} / {s.duplicates_removed}</td></tr>)}</tbody>
      </table></div>
      <div className="dim">Top users: {p.sample.map(([u, v]) => `${u} (${gb(v)} GB)`).join(', ')}</div>
    </div>
  )
}

function PeoplePreview({ p }) {
  return (
    <div className="preview">
      <div className="dim">{p.employees} employees · {p.companies.length} companies</div>
      <div className="table-wrap"><table className="mini">
        <thead><tr><th>Username key</th><th>Emp No</th><th>Emp Name</th><th>Company</th><th>Dimension</th></tr></thead>
        <tbody>{p.sample.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
      </table></div>
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
  const [inputs, setInputs] = React.useState({})
  const [busyKind, setBusyKind] = React.useState(null)
  const [errors, setErrors] = React.useState({})
  const [busy, setBusy] = React.useState(false)
  const [result, setResult] = React.useState(null)
  React.useEffect(() => { api.usageInputs().then(setInputs).catch(e => setError(e.message)) }, [])

  const upload = async (kind, file) => {
    setBusyKind(kind); setErrors(e => ({ ...e, [kind]: null })); setResult(null)
    try {
      const meta = await api.usageStore(kind, file)
      setInputs(i => ({ ...i, [kind]: meta }))
    } catch (e) { setErrors(er => ({ ...er, [kind]: e.message })) }
    setBusyKind(null)
  }
  const remove = async kind => { setInputs(await api.usageRemove(kind)); setResult(null) }
  const run = async () => {
    setBusy(true); setError(''); setResult(null)
    try { setResult(await api.usageAllocateStored()) } catch (e) { setError(e.message) }
    setBusy(false)
  }
  const common = { busy: false, onUpload: upload, onRemove: remove }
  const f = kind => ({ ...common, kind, meta: inputs[kind], busy: busyKind === kind, error: errors[kind] })
  const billCount = ['slt', 'dialog'].filter(k => inputs[k]).length
  const ready = billCount && inputs.usage && inputs.master

  return (
    <>
      <p className="caption">Split the SLT (account 003 311 8626) and Dialog (contract B698359) bills across employees by data usage. Each file is saved on the server as soon as you upload it. Each bill gives its own Excel file.</p>
      <div className="grid two">
        <Panel title="SLT bill">
          <StoredFile {...f('slt')} label="SLT bill PDF" hint="Account 003 311 8626" accept=".pdf">{p => <BillPreview bill={p} />}</StoredFile>
        </Panel>
        <Panel title="Dialog bill">
          <StoredFile {...f('dialog')} label="Dialog bill PDF" hint="Contract B698359" accept=".pdf">{p => <BillPreview bill={p} />}</StoredFile>
        </Panel>
      </div>
      <Panel title="Usage and employee data">
        <StoredFile {...f('usage')} label="Usage Excel" hint="Sheets with 'Source User' or 'username' + usage columns" accept=".xlsx">{p => <UsagePreview p={p} />}</StoredFile>
        <StoredFile {...f('master')} label="Master data (Emp.xlsx)" hint="Saved as the default for future runs" accept=".xlsx">{p => <PeoplePreview p={p} />}</StoredFile>
        <StoredFile {...f('map')} label="map.xlsx" hint="Optional · saved as the default" accept=".xlsx">{p => <PeoplePreview p={p} />}</StoredFile>
        <div className="toolbar pad">
          <span className="dim">{ready ? 'All required files are stored.' : 'Needed: at least one bill, the usage Excel and the Master data.'}</span>
          <span className="spacer" />
          <button className="btn primary" disabled={busy || !ready || !!busyKind} onClick={run}>
            {busy ? 'Processing…' : `Allocate ${billCount === 2 ? 'both bills' : 'bill'}`}
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
