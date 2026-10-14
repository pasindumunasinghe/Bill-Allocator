import React from 'react'
import { Empty, Filters, Panel, useFilter } from '../components/ui.jsx'
import { STATUS, dateTime, money } from '../format.js'
import { api } from '../api.js'
import { ResultPreview } from './Usage.jsx'

function SltDialog({ setError, go }) {
  const [latest, setLatest] = React.useState(null)
  React.useEffect(() => { api.usageLatest().then(setLatest).catch(e => setError(e.message)) }, [])
  if (!latest) return <Panel title="SLT and Dialog"><Empty>Loading…</Empty></Panel>
  return (
    <>
      <p className="caption">Latest allocation for each bill, from the SLT and Dialog page. <button className="link" onClick={() => go('usage')}>Run a new allocation</button></p>
      {['SLT', 'DIALOG'].map(t => latest[t] ? (
        <div key={t} style={{ marginBottom: 20 }}>
          <div className="dim" style={{ marginBottom: 6 }}>Processed {dateTime(latest[t].created_at)}</div>
          <ResultPreview r={latest[t]} setError={setError} />
        </div>
      ) : (
        <Panel key={t} title={t === 'SLT' ? 'SLT' : 'Dialog'}><Empty>No {t === 'SLT' ? 'SLT' : 'Dialog'} bill allocated yet.</Empty></Panel>
      ))}
    </>
  )
}

export default function Summary({ batch, setError, go }) {
  const [tab, setTab] = React.useState('A')
  const ok = (batch?.files || []).filter(f => f.status === STATUS.OK && f.group === tab)
  const { rows, props } = useFilter(ok)
  const tabs = (
    <div className="tabs" role="tablist">
      {[['A', 'Group A'], ['B', 'Group B'], ['SD', 'SLT & Dialog']].map(([g, l]) => <button key={g} role="tab" aria-selected={tab === g} className={tab === g ? 'active' : ''} onClick={() => setTab(g)}>{l}</button>)}
    </div>
  )
  if (tab === 'SD') return <>{tabs}<SltDialog setError={setError} go={go} /></>
  if (!batch) return <>{tabs}<Panel title="Bill Summary"><Empty>No batch selected.</Empty></Panel></>

  const ccTotals = {}
  for (const f of ok) {
    if (tab !== 'B') break
    const e = ccTotals[f.cost_center] ||= { company: f.related_company, cents: 0n }
    e.cents += BigInt(Math.round(Number(f.total_without_vat) * 100)) // display-only aggregation
  }

  return (
    <>
      {tabs}
      <Panel title={tab === 'A' ? 'Group A — Allocation Summary (contract 74745984)' : 'Group B — Bill Summary'} actions={<Filters search={props.search} setSearch={props.setSearch} />}>
        {!rows.length ? <Empty>No successfully processed Group {tab} bills in this batch.</Empty> : tab === 'A' ? (
          <div className="table-wrap"><table>
            <thead><tr><th>Source File Name</th><th>Subscription</th><th>Bill Period</th><th>Bill Month</th><th>Company</th><th>Dimension</th><th className="num">Allocated Amount</th></tr></thead>
            <tbody>{rows.flatMap(f => [
              ...f.allocations.map((a, i) => (
                <tr key={f.id + i} className={i === 0 ? 'group-start' : ''}>
                  <td className="file">{i === 0 ? f.file_name : ''}</td><td>{i === 0 ? f.subscription_number : ''}</td>
                  <td>{i === 0 ? f.bill_period : ''}</td><td>{i === 0 ? f.bill_month : ''}</td>
                  <td>{a.company}</td><td><code>{a.dimension}</code></td><td className="num">{money(a.amount)}</td>
                </tr>)),
              <tr key={f.id + 'calc'} className="calc-row"><td colSpan={7}>
                Total Charges {money(f.total_charges)} − VAT {money(f.vat)} = <b>{money(f.total_without_vat)}</b> ÷ 4
                {Number(f.rounding_adjustment) !== 0 && <span className="note"> · rounding adjustment {f.rounding_adjustment} applied to last company</span>}
              </td></tr>,
            ])}</tbody>
          </table></div>
        ) : (
          <div className="table-wrap"><table>
            <thead><tr><th>Source File Name</th><th>Contract</th><th>Subscription</th><th>Bill Period</th><th>Bill Month</th><th>Related Company</th><th>Cost Center</th><th className="num">Total Charges</th><th className="num">VAT</th><th className="num">Without VAT</th></tr></thead>
            <tbody>{rows.map(f => (
              <tr key={f.id}><td className="file">{f.file_name}</td><td>{f.contract_number}</td><td>{f.subscription_number}</td><td>{f.bill_period}</td><td>{f.bill_month}</td>
                <td>{f.related_company}</td><td><code>{f.cost_center}</code></td><td className="num">{money(f.total_charges)}</td><td className="num">{money(f.vat)}</td><td className="num">{money(f.total_without_vat)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Panel>
      {tab === 'B' && ok.length > 0 && (
        <Panel title="Cost Center Summary">
          <div className="table-wrap"><table>
            <thead><tr><th>Cost Center</th><th>Company</th><th className="num">Total Amount</th></tr></thead>
            <tbody>{Object.entries(ccTotals).map(([cc, e]) => (
              <tr key={cc}><td><code>{cc}</code></td><td>{e.company}</td><td className="num">{money(Number(e.cents) / 100)}</td></tr>
            ))}</tbody>
          </table></div>
        </Panel>
      )}
    </>
  )
}
