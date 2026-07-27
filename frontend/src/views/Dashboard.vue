<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="bg-white shadow-sm border-b">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 class="text-xl font-bold text-indigo-600">账单小助手</h1>
        <div class="flex items-center gap-4">
          <router-link to="/" class="nav-link" :class="{ active: $route.path === '/' }">首页</router-link>
          <router-link to="/transactions" class="nav-link" :class="{ active: $route.path === '/transactions' }">明细</router-link>
          <router-link to="/statistics" class="nav-link" :class="{ active: $route.path === '/statistics' }">统计</router-link>
          <button @click="handleLogout" class="text-gray-500 hover:text-red-500 text-sm">退出</button>
        </div>
      </div>
    </nav>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <!-- Stat Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="bg-white rounded-xl p-5 shadow-sm border">
          <p class="text-sm text-gray-500">本月收入</p>
          <p class="text-2xl font-bold text-green-600 mt-1">¥{{ formatMoney(monthlyStats.totalIncome) }}</p>
        </div>
        <div class="bg-white rounded-xl p-5 shadow-sm border">
          <p class="text-sm text-gray-500">本月支出</p>
          <p class="text-2xl font-bold text-red-500 mt-1">¥{{ formatMoney(monthlyStats.totalExpense) }}</p>
        </div>
        <div class="bg-white rounded-xl p-5 shadow-sm border">
          <p class="text-sm text-gray-500">本月结余</p>
          <p class="text-2xl font-bold mt-1" :class="monthlyStats.balance >= 0 ? 'text-indigo-600' : 'text-red-500'">
            ¥{{ formatMoney(monthlyStats.balance) }}
          </p>
        </div>
      </div>

      <!-- Quick Add Button -->
      <div class="flex justify-end">
        <button @click="showDialog = true" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg flex items-center gap-2 transition">
          <span class="text-lg leading-none">+</span> 记一笔
        </button>
      </div>

      <!-- Recent Transactions -->
      <div class="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div class="px-5 py-4 border-b flex items-center justify-between">
          <h2 class="font-semibold text-gray-800">最近记录</h2>
          <router-link to="/transactions" class="text-sm text-indigo-600 hover:text-indigo-800">查看全部 →</router-link>
        </div>
        <div v-if="recentTxns.length === 0" class="p-8 text-center text-gray-400">
          还没有记录，点击"记一笔"开始记账吧！
        </div>
        <div v-else class="divide-y">
          <div v-for="tx in recentTxns" :key="tx.id" class="px-5 py-3 flex items-center justify-between hover:bg-gray-50">
            <div class="flex items-center gap-3">
              <span class="text-2xl">{{ getCategoryIcon(tx.category, tx.type) }}</span>
              <div>
                <p class="font-medium text-gray-800">{{ tx.category }}</p>
                <p class="text-xs text-gray-400">{{ tx.date }}{{ tx.note ? ' · ' + tx.note : '' }}</p>
              </div>
            </div>
            <span class="font-semibold" :class="tx.type === 'income' ? 'text-green-600' : 'text-red-500'">
              {{ tx.type === 'income' ? '+' : '-' }}¥{{ formatMoney(tx.amount) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Monthly Chart -->
      <div class="bg-white rounded-xl shadow-sm border">
        <div class="px-5 py-4 border-b">
          <h2 class="font-semibold text-gray-800">近6个月趋势</h2>
        </div>
        <div ref="trendChartRef" class="w-full h-72"></div>
      </div>
    </main>

    <!-- Add Transaction Dialog -->
    <Teleport to="body">
      <div v-if="showDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showDialog = false">
        <div class="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md mx-4">
          <div class="flex items-center justify-between mb-5">
            <h3 class="text-lg font-semibold">新增记录</h3>
            <button @click="showDialog = false" class="text-gray-400 hover:text-gray-600">✕</button>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-4">
            <!-- Type Toggle -->
            <div class="flex bg-gray-100 rounded-lg p-1">
              <button
                type="button"
                :class="['flex-1 py-2 rounded-md text-sm font-medium transition', form.type === 'expense' ? 'bg-white shadow text-red-600' : 'text-gray-500']"
                @click="form.type = 'expense'"
              >支出</button>
              <button
                type="button"
                :class="['flex-1 py-2 rounded-md text-sm font-medium transition', form.type === 'income' ? 'bg-white shadow text-green-600' : 'text-gray-500']"
                @click="form.type = 'income'"
              >收入</button>
            </div>

            <!-- Amount -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">金额</label>
              <input v-model.number="form.amount" type="number" step="0.01" min="0.01" required
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-lg font-semibold"
                placeholder="0.00" />
            </div>

            <!-- Category -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">分类</label>
              <select v-model="form.category" required
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none">
                <option value="" disabled>选择分类</option>
                <option v-for="c in currentCategories" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>

            <!-- Date -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">日期</label>
              <input v-model="form.date" type="date" required
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" />
            </div>

            <!-- Note -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">备注（可选）</label>
              <input v-model="form.note" type="text" maxlength="100"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                placeholder="添加备注..." />
            </div>

            <div class="flex gap-3 pt-2">
              <button type="button" @click="showDialog = false"
                class="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition">
                取消
              </button>
              <button type="submit" :disabled="submitting"
                class="flex-1 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg transition font-medium">
                {{ submitting ? '保存中...' : '保存' }}
              </button>
            </div>
            <div v-if="formError" class="text-red-500 text-sm">{{ formError }}</div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import * as echarts from 'echarts'
import { getMonthlyStats, getTrendData, getUserInfo, getTransactions, createTransaction, logout } from '../api/index'

const today = new Date()
const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`

const expenseCategories = ['餐饮', '交通', '购物', '娱乐', '房租', '水电', '医疗', '教育']
const incomeCategories = ['工资', '奖金', '兼职', '投资收益', '红包']
const expenseIcons = { 餐饮: '🍜', 交通: '🚌', 购物: '🛍️', 娱乐: '🎮', 房租: '🏠', 水电: '💡', 医疗: '💊', 教育: '📚' }
const incomeIcons = { 工资: '💰', 奖金: '🎁', 兼职: '🔧', 投资收益: '📈', 红包: '🧧' }

const monthlyStats = ref({ totalIncome: 0, totalExpense: 0, balance: 0 })
const trendData = ref([])
const recentTxns = ref([])
const trendChartRef = ref(null)
let trendChart = null

const form = ref({ type: 'expense', category: '', amount: null, date: today.toISOString().slice(0, 10), note: '' })
const formError = ref('')
const submitting = ref(false)
const showDialog = ref(false)

const currentCategories = computed(() => form.value.type === 'expense' ? expenseCategories : incomeCategories)

function getCategoryIcon(cat, type) {
  const icons = type === 'expense' ? expenseIcons : incomeIcons
  return icons[cat] || (type === 'expense' ? '📝' : '💵')
}

function formatMoney(val) {
  return (val || 0).toFixed(2)
}

async function loadMonthlyStats() {
  try {
    const res = await getMonthlyStats(currentMonth)
    monthlyStats.value = res.monthlyStats
  } catch { /* ignore */ }
}

async function loadRecentTxns() {
  try {
    recentTxns.value = await getTransactions({ month: currentMonth, limit: 5 })
  } catch { /* ignore */ }
}

async function loadTrend() {
  try {
    const res = await getTrendData()
    trendData.value = res.trendData || []
    renderChart()
  } catch { /* ignore */ }
}

function renderChart() {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)

  const months = trendData.value.map(d => d.month.slice(5))
  const incomes = trendData.value.map(d => d.income)
  const expenses = trendData.value.map(d => d.expense)

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['收入', '支出'], bottom: 0 },
    grid: { top: 10, right: 20, bottom: 40, left: 50 },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}' } },
    series: [
      { name: '收入', type: 'line', data: incomes, smooth: true, itemStyle: { color: '#22c55e' }, areaStyle: { color: 'rgba(34,197,94,0.1)' } },
      { name: '支出', type: 'line', data: expenses, smooth: true, itemStyle: { color: '#ef4444' }, areaStyle: { color: 'rgba(239,68,68,0.1)' } },
    ],
  })
}

watch(() => showDialog.value, (v) => {
  if (v) {
    form.value.category = ''
    form.value.amount = null
    form.value.note = ''
    formError.value = ''
  }
})

async function handleSubmit() {
  formError.value = ''
  submitting.value = true
  try {
    await createTransaction(form.value)
    showDialog.value = false
    await loadMonthlyStats()
    await loadRecentTxns()
    await loadTrend()
  } catch (err) {
    formError.value = err.response?.data?.detail || '保存失败'
  } finally {
    submitting.value = false
  }
}

async function handleLogout() {
  await logout()
  window.location.href = '/login'
}

onMounted(async () => {
  const user = await getUserInfo()
  if (!user) return
  loadMonthlyStats()
  loadRecentTxns()
  loadTrend()
})
</script>

<style scoped>
.nav-link {
  color: #6b7280;
  font-size: 14px;
  padding: 4px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}
.nav-link:hover {
  color: #4f46e5;
  background: #eef2ff;
}
.nav-link.active {
  color: #4f46e5;
  font-weight: 600;
  background: #eef2ff;
}
</style>
