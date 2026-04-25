import { useState, useEffect, useRef } from 'react'
import { getBalance } from '../api.js'
import { paiseToRupees } from '../format.js'

export default function BalanceCard({ merchantId }) {
  const [balance, setBalance] = useState(null)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  function fetchBalance() {
    if (document.hidden) return
    getBalance(merchantId)
      .then((data) => { setBalance(data); setError(null) })
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    fetchBalance()
    intervalRef.current = setInterval(fetchBalance, 5000)
    const onVisibility = () => {
      if (!document.hidden) fetchBalance()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      clearInterval(intervalRef.current)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [merchantId])

  if (error) return <div className="p-4 text-red-600 text-sm">{error}</div>
  if (!balance) return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-1/3 mb-4" />
      <div className="h-8 bg-gray-200 rounded w-1/2" />
    </div>
  )

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-sm font-medium text-gray-500 mb-4">Balance</h2>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-500">Available</p>
          <p className="text-2xl font-bold text-gray-900">
            {paiseToRupees(balance.available_paise)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Held</p>
          <p className="text-2xl font-bold text-amber-600">
            {paiseToRupees(balance.held_paise)}
          </p>
        </div>
      </div>
      <div className="text-xs text-gray-400 space-y-0.5">
        <p>Total credited: {paiseToRupees(balance.total_credited_paise)}</p>
        <p>Total debited: {paiseToRupees(balance.total_debited_paise)}</p>
      </div>
    </div>
  )
}
