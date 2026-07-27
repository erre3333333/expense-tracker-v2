import axios from 'axios'
import { useRouter } from 'vue-router'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      const router = useRouter()
      router.push('/login').catch(() => {})
    }
    return Promise.reject(error)
  }
)

export async function register(username, password) {
  const { data } = await api.post('/auth/register', { username, password })
  return data
}

export async function login(username, password) {
  try {
    const { data } = await api.post('/auth/login', { username, password })
    localStorage.setItem('token', data.access_token)
    const meResp = await api.get('/auth/me')
    localStorage.setItem('user', JSON.stringify(meResp.data))
    return data
  } catch (err) {
    if (err.response) throw err
    throw new Error('网络连接失败，请检查网络')
  }
}

export async function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export async function getUserInfo() {
  const { data } = await api.get('/auth/me')
  return data
}

export async function getTransactions(params = {}) {
  const query = new URLSearchParams()
  if (params.month) query.set('month', params.month)
  if (params.limit) query.set('limit', params.limit)
  if (params.offset) query.set('offset', params.offset)
  const { data } = await api.get(`/transactions?${query}`)
  return data
}

export async function createTransaction(transaction) {
  const { data } = await api.post('/transactions', transaction)
  return data
}

export async function updateTransaction(id, transaction) {
  const { data } = await api.put(`/transactions/${id}`, transaction)
  return data
}

export async function deleteTransaction(id) {
  await api.delete(`/transactions/${id}`)
}

export async function getMonthlyStats(yearMonth) {
  const { data } = await api.get('/statistics/monthly', {
    params: { year_month: yearMonth },
  })
  return data
}

export async function getCategoryBreakdown(yearMonth, type = 'expense') {
  const { data } = await api.get('/statistics/category-breakdown', {
    params: { year_month: yearMonth, txn_type: type },
  })
  return data
}

export async function getTrendData() {
  const { data } = await api.get('/statistics/trend')
  return data
}

export async function analyzeExpenses(yearMonth) {
  const { data } = await api.post('/ai/analyze', { year_month: yearMonth })
  return data
}
