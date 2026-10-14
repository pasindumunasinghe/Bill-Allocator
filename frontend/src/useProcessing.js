import React from 'react'
import { api } from './api.js'
import { STATUS } from './format.js'

// Processes queued files one at a time so the progress bar reflects real server results.
export function useProcessing({ batch, setBatch, setError }) {
  const [progress, setProgress] = React.useState(null) // {done,total,current}

  const process = async (current) => {
    const b = current?.files ? current : batch
    if (!b) return
    const queue = b.files.filter(f => f.status === STATUS.QUEUED || (f.status === STATUS.UNSUPPORTED && !f.processed_at))
    if (!queue.length) { setError('There are no queued files to process.'); return }
    setError('')
    setProgress({ done: 0, total: queue.length, current: queue[0].file_name })
    for (let i = 0; i < queue.length; i++) {
      setProgress({ done: i, total: queue.length, current: queue[i].file_name })
      try { await api.processFile(queue[i].id) } catch (e) { setError(`${queue[i].file_name}: ${e.message}`) }
    }
    setProgress({ done: queue.length, total: queue.length, current: null })
    setBatch(await api.getBatch(b.id))
    setTimeout(() => setProgress(null), 2500)
  }
  return { progress, process, busy: !!progress && progress.done < progress.total }
}

export async function downloadAll(batch, setError) {
  const r = await api.reports(batch.id)
  const out = []
  for (const [key, g] of [['group_a', 'a'], ['group_b', 'b']]) {
    if (r[key].available) {
      try { out.push(await api.download(batch.id, g)) } catch (e) { setError(e.message) }
    }
  }
  if (!out.length) setError('No Group A or Group B bills in this batch — nothing to export.')
  return out
}
