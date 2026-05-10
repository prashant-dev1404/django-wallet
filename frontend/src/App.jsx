import { useState, useEffect } from 'react'
import { getMerchants } from './api.js'
import BalanceCard from './components/BalanceCard.jsx'
import PayoutForm from './components/PayoutForm.jsx'
import PayoutHistoryTable from './components/PayoutHistoryTable.jsx'
import LedgerFeed from './components/LedgerFeed.jsx'

export default function App() {
  const [merchants, setMerchants] = useState([])
  const [merchantId, setMerchantId] = useState(
    () => localStorage.getItem('merchantId') || ''
  )
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  useEffect(() => {
    console.log('[App] API URL:', import.meta.env.VITE_API_URL)
    console.log('[App] fetching merchants...')
    getMerchants()
      .then((data) => {
        console.log('[App] merchants response:', data)
        const list = Array.isArray(data) ? data : []
        setMerchants(list)
        if (!merchantId && list.length > 0) {
          const first = list[0].id
          setMerchantId(first)
          localStorage.setItem('merchantId', first)
        }
      })
      .catch((err) => {
        console.error('[App] merchants fetch failed:', err)
      })
  }, [])

  function handleMerchantChange(e) {
    const id = e.target.value
    setMerchantId(id)
    localStorage.setItem('merchantId', id)
  }

  function handlePayoutCreated() {
    setRefreshTrigger((n) => n + 1)
  }

  return (
    <div className="min-h-screen bg-brand-bg font-sans">
      <header className="bg-brand-surface border-b border-white/[0.08] px-6 py-4 flex items-center gap-4">
        <h1 className="text-xl font-semibold text-white tracking-tight">
          ✦ Playto Pay
        </h1>
        <select
          value={merchantId}
          onChange={handleMerchantChange}
          className="ml-auto bg-brand-surface2 border border-white/[0.08] rounded-lg px-3 py-1.5 text-sm text-white/80 focus:outline-none focus:border-brand-accent"
        >
          {merchants.map((m) => (
            <option key={m.id} value={m.id} className="bg-brand-surface2">
              {m.name}
            </option>
          ))}
        </select>
      </header>

      {merchantId && (
        <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-6">
              <BalanceCard key={merchantId} merchantId={merchantId} />
              <PayoutForm
                key={`form-${merchantId}`}
                merchantId={merchantId}
                onPayoutCreated={handlePayoutCreated}
              />
            </div>
            <PayoutHistoryTable
              key={`hist-${merchantId}`}
              merchantId={merchantId}
              refreshTrigger={refreshTrigger}
            />
          </div>
          <LedgerFeed
            key={`ledger-${merchantId}`}
            merchantId={merchantId}
            refreshTrigger={refreshTrigger}
          />
        </main>
      )}
    </div>
  )
}
