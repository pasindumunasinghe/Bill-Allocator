import React from 'react'
import { Empty, ErrorList, Filters, GroupBadge, Panel, StatusBadge, useFilter } from '../components/ui.jsx'
import { FAILED, STATUS } from '../format.js'

export default function Failed({ batch }) {
  const files = (batch?.files || []).filter(f => FAILED.includes(f.status) || f.status === STATUS.IGNORED)
  const { rows, props } = useFilter(files)
  return (
    <Panel title="Failed, review and ignored records — current batch" actions={<Filters {...props} statuses={[...FAILED, STATUS.IGNORED]} />}>
      <p className="caption pad">Nothing is guessed: any bill whose required fields could not be reliably identified is listed here instead of being exported as processed. Valid-contract failures are still included in their group's Excel report.</p>
      {rows.length ? (
        <div className="table-wrap"><table>
          <thead><tr><th>Source File Name</th><th>Contract Number</th><th>Group</th><th>Status</th><th>Reason</th></tr></thead>
          <tbody>{rows.map(f => (
            <tr key={f.id}><td className="file">{f.file_name}</td><td>{f.contract_number || '—'}</td><td><GroupBadge group={f.group} /></td>
              <td><StatusBadge status={f.status} /></td><td><ErrorList file={f} /></td></tr>
          ))}</tbody>
        </table></div>
      ) : <Empty>{batch ? 'No failed records in this batch.' : 'No batch selected.'}</Empty>}
    </Panel>
  )
}
