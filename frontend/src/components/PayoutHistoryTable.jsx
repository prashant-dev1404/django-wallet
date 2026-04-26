import React, { useState, useEffect, useRef } from 'react'
import { listPayouts } from '../api.js'
import { paiseToRupees, formatTimestamp, statusBadgeClasses } from '../format.js'

export default function PayoutHistoryTable({ merchantId, refreshTrigger }) {
  const [payouts, setPayouts] = useState([])
  const [error, setError] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const intervalRef = useRef(null)

  function fetchPayouts() {
    if (document.hidden) return
    listPayouts(merchantId)
      .then((data) => { setPayouts(data?.payouts ?? []); setError(null) })
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    fetchPayouts()
    intervalRef.current = setInterval(fetchPayouts, 3000)
    const onVisibility = () => { if (!document.hidden) fetchPayouts() }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      clearInterval(intervalRef.current)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [merchantId, refreshTrigger])

  if (error) return <div className="p-4 text-red-600 text-sm">{error}</div>

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Payout History</h2>

      {payouts.length === 0 ? (
        <p className="text-sm text-gray-400">No payouts yet. Use the form to create one.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-100">
                <th className="text-left pb-2 pr-3">Created</th>
                <th className="text-right pb-2 pr-3">Amount</th>
                <th className="text-left pb-2 pr-3">Status</th>
                <th className="text-left pb-2">Attempts</th>
              </tr>
            </thead>
            <tbody>
              {payouts.map((p) => (
                <React.Fragment key={p.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                    className="border-b border-gray-50 cursor-pointer hover:bg-gray-50"
                  >
                    <td className="py-2 pr-3 text-gray-600">{formatTimestamp(p.created_at)}</td>
                    <td className="py-2 pr-3 text-right font-medium">{paiseToRupees(p.amount_paise)}</td>
                    <td className="py-2 pr-3">
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${statusBadgeClasses(p.status)}`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="py-2 text-gray-500">
                      {p.attempt_count > 1 ? p.attempt_count : '—'}
                    </td>
                  </tr>
                  {expandedId === p.id && (
                    <tr>
                      <td colSpan={4} className="pb-3 pt-1 px-2">
                        <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto text-gray-600">
                          {JSON.stringify(p, null, 2)}
                        </pre>
                        {p.failure_reason && (
                          <p className="text-xs text-red-500 mt-1">{p.failure_reason}</p>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
