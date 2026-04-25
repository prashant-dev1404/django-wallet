import { useState, useEffect, useRef } from 'react'
import { getLedger } from '../api.js'
import { paiseToRupees, formatTimestamp } from '../format.js'

const BADGE = {
  CUSTOMER_PAYMENT: 'bg-blue-100 text-blue-700',
  PAYOUT_HOLD:      'bg-amber-100 text-amber-700',
  PAYOUT_REFUND:    'bg-green-100 text-green-700',
  ADJUSTMENT:       'bg-gray-100 text-gray-600',
  SEED:             'bg-gray-100 text-gray-600',
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
        setEntries(currentOffset === 0 ? data.entries : (prev) => [...prev, ...data.entries])
        setTotal(data.total_count)
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

  if (error) return <div className="p-4 text-red-600 text-sm">{error}</div>

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Ledger</h2>

      {entries.length === 0 ? (
        <p className="text-sm text-gray-400">No ledger entries yet.</p>
      ) : (
        <div className="space-y-2">
          {entries.map((e) => (
            <div key={e.id} className="flex items-start gap-3 py-2 border-b border-gray-50 last:border-0">
              <span className={`text-sm font-bold min-w-[1.5rem] ${e.entry_type === 'CREDIT' ? 'text-green-600' : 'text-red-500'}`}>
                {e.entry_type === 'CREDIT' ? '+' : '−'}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">
                    {paiseToRupees(e.amount_paise)}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${BADGE[e.reference_type] ?? BADGE.ADJUSTMENT}`}>
                    {e.reference_type}
                  </span>
                  <span className="text-xs text-gray-400 ml-auto">{formatTimestamp(e.created_at)}</span>
                </div>
                {e.description && (
                  <p className="text-xs text-gray-400 mt-0.5 truncate">{e.description}</p>
                )}
              </div>
            </div>
          ))}

          {entries.length < total && (
            <button
              onClick={loadMore}
              className="text-xs text-indigo-600 hover:underline mt-2"
            >
              Load more ({total - entries.length} remaining)
            </button>
          )}
        </div>
      )}
    </div>
  )
}
