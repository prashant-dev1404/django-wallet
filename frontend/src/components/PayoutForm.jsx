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
    <div className="bg-brand-surface rounded-xl border border-white/[0.08] p-6">
      <h2 className="text-xs font-medium text-white/40 uppercase tracking-widest mb-5">New Payout</h2>

      <div className="space-y-4">
        <div>
          <label className="block text-xs text-white/50 mb-1.5">Amount (₹)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={amountRupees}
            onChange={(e) => setAmountRupees(e.target.value)}
            placeholder="10.00"
            className="w-full bg-brand-surface2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-brand-accent transition-colors"
          />
          {amountPaise && amountPaise > 0 && (
            <p className="text-xs text-white/25 mt-1">{amountPaise} paise</p>
          )}
        </div>

        <div>
          <label className="block text-xs text-white/50 mb-1.5">Bank Account</label>
          <select
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            className="w-full bg-brand-surface2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-accent transition-colors"
          >
            {bankAccounts.map((ba) => (
              <option key={ba.id} value={ba.id} className="bg-brand-surface2">
                {ba.account_number_masked} — {ba.account_holder_name}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}
        {success && (
          <p className="text-xs text-green-400">
            Payout created: {success.id} (status: {success.status})
          </p>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full bg-brand-accent hover:bg-brand-accent-hover disabled:opacity-40 text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
        >
          {submitting ? 'Submitting…' : 'Request Payout'}
        </button>
      </div>
    </div>
  )
}
