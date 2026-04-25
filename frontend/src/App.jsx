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
    getMerchants()
      .then((data) => {
        setMerchants(data)
        if (!merchantId && data.length > 0) {
          const first = data[0].id
          setMerchantId(first)
          localStorage.setItem('merchantId', first)
        }
      })
      .catch(console.error)
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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <h1 className="text-xl font-semibold text-gray-900">Playto Pay</h1>
        <select
          value={merchantId}
          onChange={handleMerchantChange}
          className="ml-auto border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-700 bg-white"
        >
          {merchants.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </header>

      {merchantId && (
        <main className="max-w-6xl mx-auto px-6 py-6 space-y-6">
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
