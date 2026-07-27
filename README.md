# 账单小助手 v2.0

基于 FastAPI + Vue 3 的个人记账应用。

## 功能特性

- **记账** — 支持收入/支出分类，记录日常收支
- **统计** — 月度统计、分类占比饼图、趋势折线图
- **认证** — JWT Token 登录认证

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Tailwind CSS + ECharts |
| 后端 | FastAPI + aiosqlite |
| 数据库 | SQLite |

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python main.py   # uvicorn main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档

> 运行 `uvicorn main:app --reload` 启动后端服务（需切换到 backend 目录）。

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 项目结构

```
expense-tracker-v2/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── database.py          # SQLite 异步连接
│   ├── requirements.txt     # Python 依赖
│   ├── models/
│   │   └── schemas.py       # Pydantic 模型
│   └── routers/
│       ├── auth.py          # 注册/登录/鉴权
│       ├── transactions.py  # 交易 CRUD
│       └── statistics.py    # 统计分析
├── data/                    # SQLite 数据库文件（自动生成）
├── frontend/
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   ├── api/             # API 封装
│   │   └── router/          # Vue Router
│   └── package.json
└── README.md
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录 |
| GET | /api/auth/me | 获取当前用户 |
| GET | /api/transactions | 获取交易列表 |
| POST | /api/transactions | 创建交易 |
| PUT | /api/transactions/{id} | 更新交易 |
| DELETE | /api/transactions/{id} | 删除交易 |
| GET | /api/statistics/monthly | 月度统计 |
| GET | /api/statistics/category-breakdown | 分类占比 |
| GET | /api/statistics/trend | 趋势数据 |

## 环境变量

| 变量 | 说明 |
|------|------|
| DATA_DIR | 数据库存储目录（默认项目根目录下的 data/） |
