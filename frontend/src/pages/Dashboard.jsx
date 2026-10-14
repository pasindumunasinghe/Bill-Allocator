import React from 'react'
import { Card, Empty, ErrorList, GroupBadge, Panel, StatusBadge } from '../components/ui.jsx'
import { money } from '../format.js'

export default function Dashboard({ batch, go, newBatch }) {
  if (!batch) {
    return (
      <Panel title="Welcome">
        <Empty>
          <p>No processing batch is active. Start a batch and upload telecom bills (PDF, DOCX, XLSX, XLS).</p>
          <button className="btn primary" onClick={async () => { await newBatch(); go('upload') }}>Start new batch</button>
        </Empty>
      </Panel>
    )
  }
  const s = batch.summary
  return (
    <>
      <p className="caption">All figures below belong to the <b>current processing batch</b> only and include successfully processed bills. Group A and Group B are exported to separate Excel files.</p>
      <div className="grid cards">
        <Card label="Total Files Uploaded" value={s.total_files} sub={`${s.queued} queued`} />
        <Card label="Successfully Processed" value={s.processed} accent="ok" />
        <Card label="Failed Files" value={s.failed} accent={s.failed ? 'bad' : ''} sub={`${s.ignored} ignored (out of scope)`} />
        <Card label="Group A Bills" value={s.group_a} sub={`${s.group_a_processed} processed`} />
        <Card label="Group B Bills" value={s.group_b} sub={`${s.group_b_processed} processed`} />
        <Card label="Total Charges Before VAT" value={money(s.total_charges)} sub="Total Charges for Bill Period" />
        <Card label="Total VAT" value={money(s.total_vat)} />
        <Card label="Total Charges Without VAT" value={money(s.total_without_vat)} accent="navy" />
      </div>
      <Panel title="Recent files in this batch" actions={<button className="btn" onClick={() => go('upload')}>Go to Upload</button>}>
        {batch.files.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>File Name</th><th>Contract</th><th>Group</th><th>Status</th><th className="num">Total w/o VAT</th><th>Details</th></tr></thead>
            <tbody>{batch.files.slice(-8).reverse().map(f => (
              <tr key={f.id}><td className="file">{f.file_name}</td><td>{f.contract_number || '—'}</td><td><GroupBadge group={f.group} /></td>
                <td><StatusBadge status={f.status} /></td><td className="num">{money(f.total_without_vat)}</td><td><ErrorList file={f} /></td></tr>
            ))}</tbody>
          </table></div>
        ) : <Empty>No files uploaded yet.</Empty>}
      </Panel>
    </>
  )
}
