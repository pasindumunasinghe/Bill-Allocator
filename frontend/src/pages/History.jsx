import React from 'react'
import { api } from '../api.js'
import { Empty, ErrorList, Filters, GroupBadge, Panel, StatusBadge, useFilter } from '../components/ui.jsx'
import { dateTime, money } from '../format.js'

export default function History({ batch, openBatch, setError }) {
  const [batches, setBatches] = React.useState([])
  React.useEffect(() => { api.listBatches().then(setBatches).catch(e => setError(e.message)) }, [batch?.id])
  const { rows, props } = useFilter(batch?.files || [])

  return (
    <>
      <Panel title="Processing batches">
        {batches.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>Batch</th><th>Created</th><th className="num">Files</th><th className="num">Processed</th><th className="num">Failed</th><th className="num">Group A / B</th><th className="num">Total w/o VAT</th><th /></tr></thead>
            <tbody>{batches.map(b => (
              <tr key={b.id} className={b.id === batch?.id ? 'current' : ''}>
                <td><code>{b.id.slice(0, 8)}</code></td><td>{dateTime(b.created_at)}</td>
                <td className="num">{b.summary.total_files}</td><td className="num">{b.summary.processed}</td>
                <td className="num">{b.summary.failed}</td><td className="num">{b.summary.group_a} / {b.summary.group_b}</td>
                <td className="num">{money(b.summary.total_without_vat)}</td>
                <td>{b.id === batch?.id ? <span className="dim">Current</span> : <button className="btn sm" onClick={() => openBatch(b.id)}>Open</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        ) : <Empty>No batches yet.</Empty>}
      </Panel>
      {batch && (
        <Panel title="File outcomes — current batch" actions={<Filters {...props} />}>
          {rows.length ? (
            <div className="table-wrap"><table>
              <thead><tr><th>File Name</th><th>Type</th><th>Contract</th><th>Group</th><th>Status</th><th>Method</th><th className="num">Attempts</th><th>Processed</th><th>Details</th></tr></thead>
              <tbody>{rows.map(f => (
                <tr key={f.id}><td className="file">{f.file_name}</td><td>{f.file_type}</td><td>{f.contract_number || '—'}</td>
                  <td><GroupBadge group={f.group} /></td><td><StatusBadge status={f.status} /></td><td>{f.extraction_method || '—'}</td>
                  <td className="num">{f.read_attempts}</td><td>{dateTime(f.processed_at)}</td><td><ErrorList file={f} /></td></tr>
              ))}</tbody>
            </table></div>
          ) : <Empty>No files match.</Empty>}
        </Panel>
      )}
    </>
  )
}
