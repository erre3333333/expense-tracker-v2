<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="bg-white shadow-sm border-b">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 class="text-xl font-bold text-indigo-600">账单小助手</h1>
        <div class="flex items-center gap-4">
          <router-link to="/" class="nav-link" :class="{ active: $route.path === '/' }">首页</router-link>
          <router-link to="/transactions" class="nav-link" :class="{ active: $route.path === '/transactions' }">明细</router-link>
          <router-link to="/statistics" class="nav-link active">统计</router-link>
          <button @click="handleLogout" class="text-gray-500 hover:text-red-500 text-sm">退出</button>
        </div>
      </div>
    </nav>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <!-- Overall Stats -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="bg-white rounded-xl p-5 shadow-sm border">
          <p class="text-sm text-gray-500">总收入</p>
          <p class="text-2xl font-bold text-green-600 mt-1">¥{{ formatMoney(stats.monthlyStats.totalIncome) }}</p>
        </div>
        <div class="bg-white rounded-xl p-5 shadow-sm border">
          <p class="text-sm text-gray-500">总支出</p>
          <p class="text-2xl font-bold text-red-500 mt-1">¥{{ formatMoney(stats.monthlyStats.totalExpense) }}</p>
        </div>
        <div class="bg-white rounded-xl p-5 shadow-sm border">
          <p class="text-sm text-gray-500">结余</p>
          <p class="text-2xl font-bold mt-1" :class="stats.monthlyStats.balance >= 0 ? 'text-indigo-600' : 'text-red-500'">
            ¥{{ formatMoney(stats.monthlyStats.balance) }}
          </p>
        </div>
      </div>

      <!-- Month Selector -->
      <div class="bg-white rounded-xl p-4 shadow-sm border flex items-center gap-3 flex-wrap">
        <label class="text-sm font-medium text-gray-700">按月分析：</label>
        <input v-model="selectedMonth" type="month"
          class="px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" />
        <div class="flex gap-2 ml-auto">
          <button @click="activeBreakdown = 'expense'"
            :class="['px-3 py-1.5 rounded-lg text-sm transition', activeBreakdown==='expense'?'bg-red-500 text-white':'bg-gray-100 text-gray-600']">
            支出分类
          </button>
          <button @click="activeBreakdown = 'income'"
            :class="['px-3 py-1.5 rounded-lg text-sm transition', activeBreakdown==='income'?'bg-green-500 text-white':'bg-gray-100 text-gray-600']">
            收入分类
          </button>
        </div>
      </div>

      <!-- Category Chart -->
      <div class="bg-white rounded-xl shadow-sm border">
        <div class="px-5 py-4 border-b flex items-center justify-between">
          <h2 class="font-semibold text-gray-800">{{ activeBreakdown === 'expense' ? '支出' : '收入' }}分类占比</h2>
        </div>
        <div ref="pieChartRef" class="w-full h-80"></div>
      </div>

      <!-- Category Table -->
      <div class="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div class="px-5 py-4 border-b">
          <h2 class="font-semibold text-gray-800">{{ activeBreakdown === 'expense' ? '支出' : '收入' }}明细</h2>
        </div>
        <div v-if="catList.length === 0" class="p-8 text-center text-gray-400">暂无数据</div>
        <table v-else class="w-full text-sm">
          <thead class="bg-gray-50 text-gray-600">
            <tr><th class="px-5 py-2 text-left">分类</th><th class="px-5 py-2 text-right">金额</th><th class="px-5 py-2 text-right">占比</th></tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="(c, i) in catList" :key="i" class="hover:bg-gray-50">
              <td class="px-5 py-3">{{ c.category }}</td>
              <td class="px-5 py-2 text-right font-medium">{{ activeBreakdown === 'expense' ? 'text-red-500' : 'text-green-600' }}">¥{{ formatMoney(c.amount) }}</td>
              <td class="px-5 py-2 text-right text-gray-500">{{ c.percentage }}%</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Trend Chart -->
      <div class="bg-white rounded-xl shadow-sm border">
        <div class="px-5 py-4 border-b"><h2 class="font-semibold text-gray-800">近6个月趋势</h2></div>
        <div ref="trendChartRef" class="w-full h-72"></div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { getUserInfo, logout, getCategoryBreakdown, getTrendData } from '../api/index'

const expenseCategories = ['餐饮','交通','购物','娱乐','房租','水电','医疗','教育']
const incomeCategories = ['工资','奖金','兼职','投资收益','红包']
const categoryIcons = {
  餐饮:'🍜',交通:'🚌',购物:'🛍️',娱乐:'🎮',房租:'🏠',水电:'💡',医疗:'💊',教育:'📚',
  工资:'💰',奖金:'🎁',兼职:'🔧','投资收益':'📈',红包:'🧧'
}

const selectedMonth = ref('')
const activeBreakdown = ref('expense')
const pieChartRef = ref(null)
const trendChartRef = ref(null)
let pieChart = null
let trendChartInstance = null

const stats = ref({ monthlyStats: { totalIncome: 0, totalExpense: 0, balance: 0 }, categoryStats: [], trendData: [] })
const catList = ref([])

function formatMoney(v) { return (v || 0).toFixed(2) }

const pieColors = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#6366f1','#a855f7','#ec4899','#14b8a6','#f43f5e']

async function loadBreakdown() {
  try {
    const res = await getCategoryBreakdown(selectedMonth.value, activeBreakdown.value)
    catList.value = res.categoryStats || []
    renderPie()
  } catch {}
}

function renderPie() {
  if (!pieChartRef.value) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(pieChartRef.value)

  const data = catList.value.map((c, i) => ({ name: c.category, value: c.amount, itemStyle: { color: pieColors[i % pieColors.length] } }))

  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data,
    }],
  })
}

async function loadTrend() {
  try {
    const res = await getTrendData()
    stats.value = res
    renderTrend()
  } catch {}
}

function renderTrend() {
  if (!trendChartRef.value) return
  if (trendChartInstance) trendChartInstance.dispose()
  trendChartInstance = echarts.init(trendChartRef.value)

  const td = stats.value.trendData || []
  const months = td.map(d => d.month.slice(5))
  const incomes = td.map(d => d.income)
  const expenses = td.map(d => d.expense)

  trendChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['收入', '支出'], bottom: 0 },
    grid: { top: 10, right: 20, bottom: 40, left: 50 },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value' },
    series: [
      { name: '收入', type: 'bar', data: incomes, itemStyle: { color: '#22c55e' } },
      { name: '支出', type: 'bar', data: expenses, itemStyle: { color: '#ef4444' } },
    ],
  })
}

watch([activeBreakdown, () => selectedMonth.value], () => { loadBreakdown() })

async function handleLogout() {
  await logout()
  window.location.href = '/login'
}

onMounted(async () => {
  await getUserInfo()
  const now = new Date()
  selectedMonth.value = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`
  loadBreakdown()
  loadTrend()
})
</script>

<style scoped>
.nav-link { color: #6b7280; font-size: 14px; padding: 4px 12px; border-radius: 6px; transition: all 0.2s; }
.nav-link:hover { color: #4f46e5; background: #eef2ff; }
.nav-link.active { color: #4f46e5; font-weight: 600; background: #eef2ff; }
</style>
