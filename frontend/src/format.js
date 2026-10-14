const fmt = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Values arrive as exact decimal strings from the API; formatting is display-only.
export const money = v => (v === null || v === undefined || v === '' ? '—' : fmt.format(Number(v)))
export const dateTime = v => (v ? new Date(v).toLocaleString() : '—')

export const STATUS = {
  QUEUED: 'Queued',
  PROCESSING: 'Processing',
  OK: 'Processed Successfully',
  READ: 'File Read Failure',
  REVIEW: 'Needs Review',
  INVALID: 'Validation Failed',
  IGNORED: 'Ignored - Contract Not In Scope',
  UNSUPPORTED: 'Unsupported Format',
}
export const FAILED = [STATUS.READ, STATUS.REVIEW, STATUS.INVALID, STATUS.UNSUPPORTED]
