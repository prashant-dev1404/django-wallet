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

  if (error) return <div className="p-4 text-red-400 text-sm">{error}</div>
  if (!balance) return (
    <div className="bg-brand-surface rounded-xl border border-white/[0.08] p-6 animate-pulse">
      <div className="h-3 bg-white/[0.06] rounded w-1/3 mb-4" />
      <div className="h-8 bg-white/[0.06] rounded w-1/2" />
    </div>
  )

  return (
    <div className="bg-brand-surface rounded-xl border border-white/[0.08] p-6">
      <h2 className="text-xs font-medium text-white/40 uppercase tracking-widest mb-5">Balance</h2>
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div>
          <p className="text-xs text-white/40 mb-1">Available</p>
          <p className="text-2xl font-bold text-white">
            {paiseToRupees(balance.available_paise)}
          </p>
        </div>
        <div>
          <p className="text-xs text-white/40 mb-1">Held</p>
          <p className="text-2xl font-bold text-brand-accent">
            {paiseToRupees(balance.held_paise)}
          </p>
        </div>
      </div>
      <div className="text-xs text-white/30 space-y-0.5 border-t border-white/[0.06] pt-4">
        <p>Total credited: {paiseToRupees(balance.total_credited_paise)}</p>
        <p>Total debited: {paiseToRupees(balance.total_debited_paise)}</p>
      </div>
    </div>
  )
}
