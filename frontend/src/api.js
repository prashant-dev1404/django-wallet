const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

class ApiError extends Error {
  constructor(status, body) {
    super(body?.error || body?.message || `HTTP ${status}`)
    this.status = status
    this.body = body
  }
}

async function request(path, { merchantId, ...options } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(merchantId ? { 'X-Merchant-Id': merchantId } : {}),
    ...options.headers,
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body)
  return body
}

export function getMerchants() {
  return request('/api/v1/merchants')
}

export function getBalance(merchantId) {
  return request('/api/v1/balance', { merchantId })
}

export function getLedger(merchantId, { limit = 25, offset = 0 } = {}) {
  return request(`/api/v1/ledger?limit=${limit}&offset=${offset}`, { merchantId })
}

export function getBankAccounts(merchantId) {
  return request('/api/v1/bank-accounts', { merchantId })
}

export function listPayouts(merchantId, { limit = 25, offset = 0 } = {}) {
  return request(`/api/v1/payouts/list?limit=${limit}&offset=${offset}`, { merchantId })
}

export function getPayout(merchantId, id) {
  return request(`/api/v1/payouts/${id}`, { merchantId })
}

export function createPayout(merchantId, { amount_paise, bank_account_id }) {
  return request('/api/v1/payouts', {
    method: 'POST',
    merchantId,
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify({ amount_paise, bank_account_id }),
  })
}

export { ApiError }
