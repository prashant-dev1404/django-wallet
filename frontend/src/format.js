const rupeeFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
})

export function paiseToRupees(paise) {
  return rupeeFormatter.format(paise / 100)
}

export function formatTimestamp(iso) {
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))
}

export function statusBadgeClasses(status) {
  const map = {
    PENDING:    'bg-amber-500/10 text-amber-400',
    PROCESSING: 'bg-blue-500/15 text-blue-300',
    COMPLETED:  'bg-green-500/10 text-green-400',
    FAILED:     'bg-red-500/10 text-red-400',
  }
  return map[status] ?? 'bg-white/[0.05] text-white/35'
}
