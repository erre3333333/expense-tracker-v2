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

      <!-- AI Analysis -->
      <div class="bg-white rounded-xl shadow-sm border">
        <div class="px-5 py-4 border-b flex items-center justify-between">
          <h2 class="font-semibold text-gray-800">🤖 AI 智能分析</h2>
          <div class="flex items-center gap-2">
            <button @click="showKeyModal = true"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition bg-gray-100 text-gray-600 hover:bg-gray-200">
              {{ groqKey ? '🔑 已设置' : '🔑 设置 Key' }}
            </button>
            <button @click="runAIAnalysis"
              :disabled="analyzing || !groqKey"
              :class="['px-4 py-2 rounded-lg text-sm font-medium transition',
                (analyzing || !groqKey) ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-indigo-500 text-white hover:bg-indigo-600']">
              {{ analyzing ? '分析中...' : '开始分析' }}
            </button>
          </div>
        </div>

        <!-- 分析中状态 -->
        <div v-if="analyzing" class="p-6">
          <div class="text-center mb-4">
            <div class="inline-flex items-center gap-3 text-indigo-500">
              <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span class="font-medium">AI 多 Agent 团队协作分析中...</span>
            </div>
          </div>

          <!-- Agent 进度面板 -->
          <div class="grid grid-cols-2 gap-3 max-w-lg mx-auto">
            <div v-for="(status, agent) in agentStatuses" :key="agent"
              class="flex items-center gap-2 p-3 rounded-lg border text-sm"
              :class="{
                'bg-indigo-50 border-indigo-200': status === 'working',
                'bg-green-50 border-green-200': status === 'done',
                'bg-gray-50 border-gray-200': status === 'pending'
              }">
              <span class="text-lg">
                {{ status === 'done' ? '✅' : status === 'working' ? '⚡' : '⏳' }}
              </span>
              <span :class="{
                'text-indigo-700': status === 'working',
                'text-green-700': status === 'done',
                'text-gray-500': status === 'pending'
              }">{{ agent }}</span>
            </div>
          </div>

          <!-- 实时日志 -->
          <div v-if="agentLogs.length" class="mt-4 bg-gray-900 rounded-lg p-4 max-h-48 overflow-y-auto">
            <div v-for="(log, i) in agentLogs" :key="i" class="text-xs font-mono"
              :class="{
                'text-green-400': log.type === 'complete',
                'text-yellow-400': log.type === 'progress',
                'text-red-400': log.type === 'error',
                'text-gray-400': log.type === 'start' || log.type === 'agent_start'
              }">
              <span class="text-gray-500">[{{ log.agent }}]</span> {{ log.status }}
            </div>
          </div>
        </div>

        <!-- 分析结果 -->
        <div v-else-if="analysisResult" class="p-5 space-y-5">
          <!-- 数据概览 -->
          <div class="bg-gray-50 rounded-lg p-4">
            <div class="grid grid-cols-3 gap-4 text-center">
              <div>
                <p class="text-sm text-gray-500">月收入</p>
                <p class="text-lg font-bold text-green-600">¥{{ formatMoney(analysisResult.data_summary?.total_income) }}</p>
              </div>
              <div>
                <p class="text-sm text-gray-500">月支出</p>
                <p class="text-lg font-bold text-red-500">¥{{ formatMoney(analysisResult.data_summary?.total_expense) }}</p>
              </div>
              <div>
                <p class="text-sm text-gray-500">结余</p>
                <p class="text-lg font-bold" :class="(analysisResult.data_summary?.balance || 0) >= 0 ? 'text-indigo-600' : 'text-red-500'">
                  ¥{{ formatMoney(analysisResult.data_summary?.balance) }}
                </p>
              </div>
            </div>
          </div>

          <!-- 趋势分析 -->
          <div v-if="analysisResult.analysis?.trend" class="border rounded-lg p-4">
            <h3 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <span class="w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm">📈</span>
              消费趋势分析
            </h3>
            <p class="text-gray-600 mb-3">{{ analysisResult.analysis.trend.summary }}</p>
            <div v-if="analysisResult.analysis.trend.key_findings" class="space-y-2">
              <div v-for="(finding, i) in analysisResult.analysis.trend.key_findings" :key="i"
                class="flex items-start gap-2 text-sm text-gray-600">
                <span class="text-blue-500 mt-0.5">•</span>
                <span>{{ finding }}</span>
              </div>
            </div>
            <div v-if="analysisResult.analysis.trend.trend" class="mt-3 inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium"
              :class="{
                'bg-red-100 text-red-700': analysisResult.analysis.trend.trend === '上升',
                'bg-green-100 text-green-700': analysisResult.analysis.trend.trend === '下降',
                'bg-gray-100 text-gray-700': analysisResult.analysis.trend.trend === '稳定'
              }">
              趋势：{{ analysisResult.analysis.trend.trend }}
            </div>
          </div>

          <!-- 异常检测 -->
          <div v-if="analysisResult.analysis?.anomaly" class="border rounded-lg p-4">
            <h3 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <span class="w-8 h-8 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center text-sm">🔍</span>
              异常消费检测
            </h3>
            <div v-if="analysisResult.analysis.anomaly.risk_level"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium mb-3"
              :class="{
                'bg-green-100 text-green-700': analysisResult.analysis.anomaly.risk_level === '低',
                'bg-yellow-100 text-yellow-700': analysisResult.analysis.anomaly.risk_level === '中',
                'bg-red-100 text-red-700': analysisResult.analysis.anomaly.risk_level === '高'
              }">
              风险等级：{{ analysisResult.analysis.anomaly.risk_level }}
            </div>
            <div v-if="analysisResult.analysis.anomaly.anomalies?.length" class="space-y-3">
              <div v-for="(item, i) in analysisResult.analysis.anomaly.anomalies" :key="i"
                class="bg-orange-50 rounded-lg p-3 text-sm">
                <div class="flex items-center justify-between mb-1">
                  <span class="font-medium text-orange-800">{{ item.type }}</span>
                  <span class="text-orange-600">¥{{ formatMoney(item.amount) }}</span>
                </div>
                <p class="text-orange-700">{{ item.description }}</p>
                <p v-if="item.suggestion" class="text-orange-600 text-xs mt-1">💡 {{ item.suggestion }}</p>
              </div>
            </div>
            <p v-else class="text-gray-500 text-sm">未发现明显异常消费</p>
          </div>

          <!-- 预算建议 -->
          <div v-if="analysisResult.analysis?.budget" class="border rounded-lg p-4">
            <h3 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <span class="w-8 h-8 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-sm">📊</span>
              预算管理建议
            </h3>
            <p class="text-gray-600 mb-3">{{ analysisResult.analysis.budget.budget_assessment }}</p>
            <div v-if="analysisResult.analysis.budget.adjustments?.length" class="space-y-2">
              <div v-for="(adj, i) in analysisResult.analysis.budget.adjustments" :key="i"
                class="flex items-center justify-between bg-green-50 rounded-lg p-3 text-sm">
                <div>
                  <span class="font-medium text-green-800">{{ adj.category }}</span>
                  <span class="text-green-600 ml-2">{{ adj.reason }}</span>
                </div>
                <div class="flex items-center gap-2 text-green-700">
                  <span>¥{{ formatMoney(adj.current) }}</span>
                  <span>→</span>
                  <span class="font-bold">¥{{ formatMoney(adj.suggested) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 省钱建议 -->
          <div v-if="analysisResult.analysis?.savings" class="border rounded-lg p-4">
            <h3 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <span class="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center text-sm">💰</span>
              省钱小妙招
            </h3>
            <div v-if="analysisResult.analysis.savings.tips?.length" class="space-y-3">
              <div v-for="(tip, i) in analysisResult.analysis.savings.tips" :key="i"
                class="bg-purple-50 rounded-lg p-3 text-sm">
                <div class="flex items-center justify-between mb-1">
                  <span class="font-medium text-purple-800">{{ tip.area }}</span>
                  <span class="text-purple-600">预计省 ¥{{ formatMoney(tip.estimated_saving) }}</span>
                </div>
                <p class="text-purple-700">{{ tip.method }}</p>
                <p v-if="tip.impact" class="text-purple-500 text-xs mt-1">生活质量影响：{{ tip.impact }}</p>
              </div>
            </div>
            <div v-if="analysisResult.analysis.savings.total_potential_saving" class="mt-3 text-center">
              <span class="text-sm text-gray-500">预计每月可节省</span>
              <span class="text-xl font-bold text-purple-600 ml-2">¥{{ formatMoney(analysisResult.analysis.savings.total_potential_saving) }}</span>
            </div>
          </div>

          <!-- 原始分析文本（JSON解析失败时） -->
          <div v-if="analysisResult.analysis?.trend?.raw_text" class="bg-gray-50 rounded-lg p-4">
            <p class="text-sm text-gray-500 mb-2">AI 分析原文：</p>
            <pre class="text-sm text-gray-700 whitespace-pre-wrap">{{ analysisResult.analysis.trend.raw_text }}</pre>
          </div>
        </div>

        <!-- 无数据提示 -->
        <div v-else class="p-8 text-center text-gray-400">
          <p v-if="!groqKey">请先设置 API Key</p>
          <p v-else>点击"开始分析"，AI 团队将为您的消费数据提供深度洞察</p>
        </div>
      </div>
    </main>

    <!-- Groq Key 设置弹窗 -->
    <div v-if="showKeyModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
        <h3 class="text-lg font-bold text-gray-800 mb-2">设置 Groq API Key</h3>
        <p class="text-sm text-gray-500 mb-4">
          免费获取：<a href="https://open.bigmodel.cn/" target="_blank" class="text-indigo-500 underline">open.bigmodel.cn</a>
          <br>注册后在"API密钥管理"创建即可，GLM-4-Flash 永久免费。
        </p>
        <input v-model="keyInput" type="password" placeholder="输入你的智谱AI API Key..."
          class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm" />
        <div class="flex justify-end gap-3 mt-5">
          <button @click="showKeyModal = false" class="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">取消</button>
          <button @click="saveGroqKey" class="px-4 py-2 rounded-lg text-sm bg-indigo-500 text-white hover:bg-indigo-600">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { getUserInfo, logout, getCategoryBreakdown, getTrendData, analyzeExpenses } from '../api/index'

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
const analyzing = ref(false)
const analysisResult = ref(null)
const showKeyModal = ref(false)
const keyInput = ref('')
const groqKey = ref(localStorage.getItem('groq_api_key') || 'sk-yNyarp9QLUZV8NYybNl1x8LbRPg2QzwfvsfB7iJXJ5nm971j')
const agentStatuses = ref({})
const agentLogs = ref([])

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

async function runAIAnalysis() {
  if (!selectedMonth.value || !groqKey.value) return
  analyzing.value = true
  analysisResult.value = null
  agentStatuses.value = {
    '趋势分析师': 'pending',
    '异常检测专家': 'pending',
    '预算顾问': 'pending',
    '省钱教练': 'pending',
  }
  agentLogs.value = []

  try {
    // 使用 WebSocket 流式模式
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ai/analyze/stream`)

    ws.onopen = () => {
      const userInfo = JSON.parse(localStorage.getItem('user') || '{}')
      ws.send(JSON.stringify({
        year_month: selectedMonth.value,
        api_key: groqKey.value,
        user_id: userInfo.id,
      }))
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      // 记录日志
      agentLogs.value.push({
        type: msg.type,
        agent: msg.agent || 'System',
        status: msg.status || msg.message || '',
      })

      // 限制日志数量
      if (agentLogs.value.length > 50) {
        agentLogs.value = agentLogs.value.slice(-30)
      }

      // 更新 Agent 状态
      if (msg.type === 'agent_start' && msg.agent) {
        agentStatuses.value[msg.agent] = 'working'
      } else if (msg.type === 'agent_complete' && msg.agent) {
        agentStatuses.value[msg.agent] = 'done'
      }

      // 分析完成
      if (msg.type === 'complete') {
        analysisResult.value = msg
        analyzing.value = false
        ws.close()
      }

      // 错误
      if (msg.type === 'error') {
        analysisResult.value = { success: false, message: msg.message }
        analyzing.value = false
        ws.close()
      }
    }

    ws.onerror = () => {
      // WebSocket 失败，降级到 HTTP 模式
      fallbackHTTP()
    }

    ws.onclose = () => {
      if (analyzing.value) {
        // 连接异常关闭，降级到 HTTP
        fallbackHTTP()
      }
    }
  } catch (e) {
    fallbackHTTP()
  }
}

async function fallbackHTTP() {
  try {
    const result = await analyzeExpenses(selectedMonth.value, groqKey.value)
    analysisResult.value = result
  } catch (e) {
    analysisResult.value = { success: false, message: e.response?.data?.detail || '分析失败，请稍后重试' }
  } finally {
    analyzing.value = false
  }
}

function saveGroqKey() {
  if (keyInput.value.trim()) {
    groqKey.value = keyInput.value.trim()
    localStorage.setItem('groq_api_key', groqKey.value)
    showKeyModal.value = false
    keyInput.value = ''
  }
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
