// All backend communication lives here; UI components never call fetch directly.
const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* non-JSON */ }
    throw new Error(detail)
  }
  return res
}

export const api = {
  health: () => request('/api/health').then(r => r.json()),
  createBatch: () => request('/api/batches', { method: 'POST' }).then(r => r.json()),
  listBatches: () => request('/api/batches').then(r => r.json()),
  getBatch: id => request(`/api/batches/${id}`).then(r => r.json()),
  upload: (id, files) => {
    const fd = new FormData()
    for (const f of files) fd.append('files', f)
    return request(`/api/batches/${id}/files`, { method: 'POST', body: fd }).then(r => r.json())
  },
  processFile: fileId => request(`/api/files/${fileId}/process`, { method: 'POST' }).then(r => r.json()),
  clearQueue: id => request(`/api/batches/${id}/queue`, { method: 'DELETE' }).then(r => r.json()),
  reports: id => request(`/api/batches/${id}/reports`).then(r => r.json()),
  download: async (id, group) => {
    const res = await request(`/api/batches/${id}/reports/group-${group}`)
    const cd = res.headers.get('content-disposition') || ''
    const name = (cd.match(/filename="(.+?)"/) || [])[1] || `report-${group}.xlsx`
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = Object.assign(document.createElement('a'), { href: url, download: name })
    document.body.appendChild(a); a.click(); a.remove()
    URL.revokeObjectURL(url)
    return name
  },
}
