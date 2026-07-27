<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="bg-white shadow-sm border-b">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 class="text-xl font-bold text-indigo-600">账单小助手</h1>
        <div class="flex items-center gap-4">
          <router-link to="/" class="nav-link" :class="{ active: $route.path === '/' }">首页</router-link>
          <router-link to="/transactions" class="nav-link active">明细</router-link>
          <router-link to="/statistics" class="nav-link" :class="{ active: $route.path === '/statistics' }">统计</router-link>
          <button @click="handleLogout" class="text-gray-500 hover:text-red-500 text-sm">退出</button>
        </div>
      </div>
    </nav>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div class="bg-white rounded-xl p-4 shadow-sm border flex items-center justify-between flex-wrap gap-3">
        <label class="flex items-center gap-3 text-sm font-medium text-gray-700">
          月份：
          <input v-model="selectedMonth" type="month"
            class="px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" />
        </label>
        <button @click="openAdd" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg transition">+ 记一笔</button>
      </div>

      <div class="flex gap-2">
        <button v-for="tab in tabs" :key="tab.value"
          @click="activeTab = tab.value"
          :class="['px-4 py-2 rounded-lg text-sm font-medium transition',
            activeTab === tab.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 border hover:border-indigo-300']">
          {{ tab.label }}
        </button>
      </div>

      <div class="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div v-if="filteredTxns.length === 0" class="p-12 text-center text-gray-400">暂无记录</div>
        <div v-else class="divide-y">
          <div v-for="tx in filteredTxns" :key="tx.id" class="px-5 py-4 flex items-center justify-between hover:bg-gray-50">
            <div class="flex items-center gap-4 flex-1 min-w-0">
              <span class="text-2xl flex-shrink-0">{{ getCategoryIcon(tx.category, tx.type) }}</span>
              <div class="min-w-0">
                <p class="font-medium text-gray-800">{{ tx.category }}</p>
                <div class="flex items-center gap-2 text-xs text-gray-400">
                  <span>{{ tx.date }}</span><span v-if="tx.note">· {{ tx.note }}</span>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-3 flex-shrink-0">
              <span class="font-semibold whitespace-nowrap" :class="tx.type === 'income' ? 'text-green-600' : 'text-red-500'">
                {{ tx.type === 'income' ? '+' : '-' }}¥{{ formatMoney(tx.amount) }}
              </span>
              <button @click="openEdit(tx)" class="text-gray-400 hover:text-indigo-600" title="编辑">&#9998;</button>
              <button @click="doDelete(tx.id)" class="text-gray-400 hover:text-red-600" title="删除">&#10005;</button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <Teleport to="body">
      <div v-if="showDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closeDialog">
        <div class="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md mx-4">
          <h3 class="text-lg font-semibold mb-5">{{ editingTxn ? '编辑记录' : '新增记录' }}</h3>
          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div class="flex bg-gray-100 rounded-lg p-1">
              <button type="button" :class="['flex-1 py-2 rounded-md text-sm font-medium transition', form.type==='expense'?'bg-white shadow text-red-600':'text-gray-500']" @click="form.type='expense'">支出</button>
              <button type="button" :class="['flex-1 py-2 rounded-md text-sm font-medium transition', form.type==='income'?'bg-white shadow text-green-600':'text-gray-500']" @click="form.type='income'">收入</button>
            </div>
            <div><label class="block text-sm font-medium text-gray-700 mb-1">金额</label>
              <input v-model.number="form.amount" type="number" step="0.01" min="0.01" required
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-lg font-semibold" /></div>
            <div><label class="block text-sm font-medium text-gray-700 mb-1">分类</label>
              <select v-model="form.category" required class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none">
                <option value="" disabled>选择分类</option>
                <option v-for="c in currentCategories" :key="c" :value="c">{{ c }}</option></select></div>
            <div><label class="block text-sm font-medium text-gray-700 mb-1">日期</label>
              <input v-model="form.date" type="date" required
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" /></div>
            <div><label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
              <input v-model="form.note" type="text" maxlength="100"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" /></div>
            <div v-if="formError" class="text-red-500 text-sm">{{ formError }}</div>
            <div class="flex gap-3 pt-2">
              <button type="button" @click="closeDialog" class="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">取消</button>
              <button type="submit" :disabled="submitting" class="flex-1 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg transition font-medium">
                {{ submitting ? '保存中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getTransactions, createTransaction, updateTransaction, deleteTransaction, getUserInfo, logout } from '../api/index'

const today = new Date()
const selectedMonth = ref(`${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`)
const allTxns = ref([])
const showDialog = ref(false)
const editingTxn = ref(null)
const formError = ref('')
const submitting = ref(false)

const form = ref({ type: 'expense', category: '', amount: null, date: today.toISOString().slice(0,10), note: '' })

const expenseCategories = ['餐饮','交通','购物','娱乐','房租','水电','医疗','教育']
const incomeCategories = ['工资','奖金','兼职','投资收益','红包']
const categoryIcons = {
  餐饮:'🍜',交通:'🚌',购物:'🛍️',娱乐:'🎮',房租:'🏠',水电:'💡',医疗:'💊',教育:'📚',
  工资:'💰',奖金:'🎁',兼职:'🔧','投资收益':'📈',红包:'🧧'
}

const tabs = [
  { label: '全部', value: '' },
  { label: '支出', value: 'expense' },
  { label: '收入', value: 'income' },
]
const activeTab = ref('')

const currentCategories = computed(() => form.value.type === 'expense' ? expenseCategories : incomeCategories)
const filteredTxns = computed(() => {
  let list = allTxns.value
  if (activeTab.value) list = list.filter(t => t.type === activeTab.value)
  return list
})

function getCategoryIcon(cat, type) {
  return categoryIcons[cat] || (type === 'expense' ? '📝' : '💵')
}
function formatMoney(v) { return (v || 0).toFixed(2) }

async function loadData() {
  try {
    allTxns.value = await getTransactions({ month: selectedMonth.value, limit: 500 })
  } catch {}
}

function openAdd() {
  editingTxn.value = null
  form.value = { type: 'expense', category: '', amount: null, date: today.toISOString().slice(0,10), note: '' }
  formError.value = ''
  showDialog.value = true
}

function openEdit(tx) {
  editingTxn.value = tx
  form.value = { type: tx.type, category: tx.category, amount: tx.amount, date: tx.date, note: tx.note || '' }
  formError.value = ''
  showDialog.value = true
}

function closeDialog() {
  showDialog.value = false
  editingTxn.value = null
}

async function handleSubmit() {
  formError.value = ''
  submitting.value = true
  try {
    if (editingTxn.value) {
      await updateTransaction(editingTxn.value.id, form.value)
    } else {
      await createTransaction(form.value)
    }
    closeDialog()
    await loadData()
  } catch (err) {
    formError.value = err.response?.data?.detail || '保存失败'
  } finally {
    submitting.value = false
  }
}

async function doDelete(id) {
  if (!confirm('确定删除这条记录？')) return
  try { await deleteTransaction(id); await loadData() } catch (e) { formError.value = e.response?.data?.detail || '删除失败' }
}

async function handleLogout() {
  await logout()
  window.location.href = '/login'
}

onMounted(async () => {
  await getUserInfo()
  await loadData()
})
</script>

<style scoped>
.nav-link { color: #6b7280; font-size: 14px; padding: 4px 12px; border-radius: 6px; transition: all 0.2s; }
.nav-link:hover { color: #4f46e5; background: #eef2ff; }
.nav-link.active { color: #4f46e5; font-weight: 600; background: #eef2ff; }
</style>
