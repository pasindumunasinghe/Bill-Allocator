import React from 'react'
import { api } from '../api.js'
import { Empty, ErrorList, Filters, GroupBadge, Panel, StatusBadge, useFilter } from '../components/ui.jsx'
import { STATUS } from '../format.js'
import { downloadAll, useProcessing } from '../useProcessing.js'

export default function Upload(ctx) {
  const { batch, setBatch, newBatch, setError } = ctx
  const input = React.useRef()
  const [dragging, setDragging] = React.useState(false)
  const [uploading, setUploading] = React.useState(false)
  const { progress, process, busy } = useProcessing(ctx)
  const files = batch?.files || []
  const { rows, props } = useFilter(files)
  const queued = files.filter(f => f.status === STATUS.QUEUED).length
  const retryable = files.filter(f => f.status !== STATUS.OK && f.status !== STATUS.IGNORED && f.status !== STATUS.USAGE).length
  const processedAny = files.some(f => f.processed_at)

  const upload = async list => {
    if (!list?.length) return
    setUploading(true); setError('')
    try {
      const b = batch || await newBatch()
      const updated = await api.upload(b.id, Array.from(list))
      setBatch(updated)
      setUploading(false)
      await process(updated) // calculate immediately after upload
    } catch (e) { setError(`Upload failed: ${e.message}`); setUploading(false) }
    if (input.current) input.current.value = ''
  }

  const clear = async () => {
    // Drop unprocessed files, then start a fresh batch. Processed results stay in Processing History.
    try { await api.clearQueue(batch.id); await newBatch() } catch (e) { setError(e.message) }
  }

  return (
    <>
      <div className={`dropzone ${dragging ? 'drag' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files) }}>
        <div className="dz-icon">⇪</div>
        <p><b>Drag & drop telecom bills here</b> or use Upload Bills.</p>
        <p className="dim">PDF (text or scanned with OCR), DOCX, XLSX, XLS · multiple files · each processed independently</p>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.xlsx,.xls" onChange={e => upload(e.target.files)} />
      </div>

      <div className="toolbar">
        <button className="btn primary" disabled={uploading || busy} onClick={() => input.current.click()}>{uploading ? 'Uploading…' : 'Upload Bills'}</button>
        <button className="btn navy" disabled={!retryable || busy} onClick={() => process()}
          title={queued ? '' : 'Re-process files that failed or need review'}>Process Bills{retryable ? ` (${retryable})` : ''}</button>
        <button className="btn" disabled={!files.length || busy || uploading} onClick={clear}>Clear Queue</button>
        <button className="btn" disabled={!processedAny || busy || queued > 0} onClick={() => downloadAll(batch, setError)}
          title={queued ? 'Process queued files first' : ''}>Download Reports</button>
        <span className="spacer" />
        <button className="btn ghost" disabled={busy} onClick={async () => { await newBatch() }}>New Batch</button>
      </div>

      {progress && (
        <div className="progress-box" aria-live="polite">
          <div className="progress-text">
            {progress.done < progress.total ? <>Processing <b>{progress.current}</b> ({progress.done + 1} of {progress.total})</> : <>Finished processing {progress.total} file(s)</>}
          </div>
          <div className="progress"><div style={{ width: `${(progress.done / progress.total) * 100}%` }} /></div>
        </div>
      )}

      {files.some(f => f.status === STATUS.USAGE) && (
        <div className="alert warn">SLT / Dialog B698359 bills are allocated by usage.
          <button className="link" onClick={() => ctx.go('usage')}>Open Usage Allocation</button></div>
      )}
      <Panel title="Upload queue" actions={<Filters {...props} />}>
        {rows.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>File Name</th><th>File Type</th><th>Detected Contract</th><th>Processing Group</th><th>Processing Status</th><th>Error Details</th></tr></thead>
            <tbody>{rows.map(f => (
              <tr key={f.id}>
                <td className="file">{f.file_name}</td>
                <td><span className="ftype">{f.file_type}</span></td>
                <td>{f.contract_number || '—'}{f.contract_source === 'filename' && <div className="note">from filename</div>}</td>
                <td><GroupBadge group={f.group} /></td>
                <td><StatusBadge status={f.status} /></td>
                <td><ErrorList file={f} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        ) : <Empty>{files.length ? 'No files match the filters.' : 'The queue is empty. Upload bills to begin.'}</Empty>}
      </Panel>
    </>
  )
}
