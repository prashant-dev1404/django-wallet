import { useState, useEffect, useRef } from 'react'
import { getLedger } from '../api.js'
import { paiseToRupees, formatTimestamp } from '../format.js'

const BADGE = {
  CUSTOMER_PAYMENT: 'bg-blue-500/15 text-blue-300',
  PAYOUT_HOLD:      'bg-amber-500/10 text-amber-400',
  PAYOUT_REFUND:    'bg-green-500/10 text-green-400',
  ADJUSTMENT:       'bg-white/[0.05] text-white/35',
  SEED:             'bg-white/[0.05] text-white/35',
}

export default function LedgerFeed({ merchantId, refreshTrigger }) {
  const [entries, setEntries] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  function fetchEntries(currentOffset = 0) {
    if (document.hidden) return
    getLedger(merchantId, { limit: 25, offset: currentOffset })
      .then((data) => {
        const newEntries = data?.entries ?? []
        setEntries(currentOffset === 0 ? newEntries : (prev) => [...prev, ...newEntries])
        setTotal(data?.total_count ?? 0)
        setError(null)
      })
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    setOffset(0)
    fetchEntries(0)
    intervalRef.current = setInterval(() => fetchEntries(0), 5000)
    const onVisibility = () => { if (!document.hidden) fetchEntries(0) }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      clearInterval(intervalRef.current)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [merchantId, refreshTrigger])

  function loadMore() {
    const next = offset + 25
    setOffset(next)
    fetchEntries(next)
  }

  if (error) return <div className="p-4 text-red-400 text-sm">{error}</div>

  return (
    <div className="bg-brand-surface rounded-xl border border-white/[0.08] p-6">
      <h2 className="text-xs font-medium text-white/40 uppercase tracking-widest mb-5">Ledger</h2>

      {entries.length === 0 ? (
        <p className="text-sm text-white/30">No ledger entries yet.</p>
      ) : (
        <div className="space-y-1">
          {entries.map((e) => (
            <div key={e.id} className="flex items-start gap-3 py-2.5 border-b border-white/[0.04] last:border-0">
              <span className={`text-sm font-bold min-w-[1.5rem] ${e.entry_type === 'CREDIT' ? 'text-green-400' : 'text-red-400'}`}>
                {e.entry_type === 'CREDIT' ? '+' : '−'}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white">
                    {paiseToRupees(e.amount_paise)}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${BADGE[e.reference_type] ?? BADGE.ADJUSTMENT}`}>
                    {e.reference_type}
                  </span>
                  <span className="text-xs text-white/25 ml-auto">{formatTimestamp(e.created_at)}</span>
                </div>
                {e.description && (
                  <p className="text-xs text-white/30 mt-0.5 truncate">{e.description}</p>
                )}
              </div>
            </div>
          ))}

          {entries.length < total && (
            <button
              onClick={loadMore}
              className="text-xs text-brand-accent hover:text-brand-accent-hover mt-2 transition-colors"
            >
              Load more ({total - entries.length} remaining)
            </button>
          )}
        </div>
      )}
    </div>
  )
}
