import { useState, useEffect } from 'react'
import { getBankAccounts, createPayout, ApiError } from '../api.js'

export default function PayoutForm({ merchantId, onPayoutCreated }) {
  const [bankAccounts, setBankAccounts] = useState([])
  const [bankAccountId, setBankAccountId] = useState('')
  const [amountRupees, setAmountRupees] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  useEffect(() => {
    getBankAccounts(merchantId)
      .then((data) => {
        setBankAccounts(data)
        if (data.length > 0) setBankAccountId(data[0].id)
      })
      .catch(console.error)
  }, [merchantId])

  const amountPaise = amountRupees ? Math.round(parseFloat(amountRupees) * 100) : null

  async function handleSubmit() {
    setError(null)
    setSuccess(null)

    if (!amountRupees || isNaN(parseFloat(amountRupees)) || parseFloat(amountRupees) <= 0) {
      setError('Enter a valid amount greater than zero.')
      return
    }
    if (!bankAccountId) {
      setError('Select a bank account.')
      return
    }

    setSubmitting(true)
    try {
      const payout = await createPayout(merchantId, {
        amount_paise: amountPaise,
        bank_account_id: bankAccountId,
      })
      setSuccess(payout)
      setAmountRupees('')
      onPayoutCreated?.()
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.body?.error || e.message)
      } else {
        setError('Unexpected error. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-sm font-medium text-gray-500 mb-4">New Payout</h2>

      <div className="space-y-3">
        <div>
          <label className="block text-xs text-gray-600 mb-1">Amount (₹)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={amountRupees}
            onChange={(e) => setAmountRupees(e.target.value)}
            placeholder="10.00"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          {amountPaise && amountPaise > 0 && (
            <p className="text-xs text-gray-400 mt-1">{amountPaise} paise</p>
          )}
        </div>

        <div>
          <label className="block text-xs text-gray-600 mb-1">Bank Account</label>
          <select
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-white"
          >
            {bankAccounts.map((ba) => (
              <option key={ba.id} value={ba.id}>
                {ba.account_number_masked} — {ba.account_holder_name}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}
        {success && (
          <p className="text-xs text-green-600">
            Payout created: {success.id} (status: {success.status})
          </p>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded px-4 py-2"
        >
          {submitting ? 'Submitting…' : 'Request Payout'}
        </button>
      </div>
    </div>
  )
}
