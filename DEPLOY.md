# Expense Tracker v2 — Railway 部署指南

## 技术栈

- **前端**: Vue 3 + Vite + Tailwind + ECharts
- **后端**: FastAPI + aiosqlite + JWT
- **数据库**: SQLite（文件存储）
- **部署**: Railway（Dockerfile 方案）

## 前置条件

1. GitHub 账号 + 仓库
2. Railway 账号（https://railway.app）
3. Railway CLI（`npm i -g @railway/cli`）
4. Node.js 20+（本地构建前端用）

## 项目结构

```
expense-tracker-v2/
├── backend/
│   ├── main.py              # FastAPI 入口，含静态文件挂载 + SPA catch-all
│   ├── database.py          # SQLite 数据库
│   ├── requirements.txt     # Python 依赖
│   ├── routers/             # API 路由
│   └── models/              # Pydantic 模型
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js       # build.outDir: 'dist'
├── Dockerfile               # 部署用
├── railway.json             # Railway 配置
├── .gitignore
└── README.md
```

## 部署步骤

### 1. 代码准备

```bash
# 确保本地能正常运行
cd backend && pip install -r requirements.txt && python main.py
cd frontend && npm install && npm run dev
```

### 2. Git 推送到 GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/expense-tracker-v2.git
git push -u origin main
```

### 3. Railway 创建项目

```bash
# 登录
railway login

# 在 Railway 网页端创建项目，或：
railway init

# 关联 GitHub 仓库（网页端操作更方便）
# Railway Dashboard → New Project → Deploy from GitHub Repo
```

### 4. 设置环境变量

在 Railway Dashboard → Service → Variables 中添加：

| 变量 | 值 | 说明 |
|------|-----|------|
| `SECRET_KEY` | 任意随机字符串 | JWT 密钥 |

> Railway 会自动注入 `PORT` 环境变量，无需手动设置。

### 5. 部署

```bash
# 方式一：GitHub push 自动触发（推荐）
git push

# 方式二：手动触发
railway service deploy
```

### 6. 添加域名

```bash
railway domain
# 输出类似：https://expense-tracker-v2-production.up.railway.app
```

### 7. 验证

```bash
# Health check
curl https://你的域名.up.railway.app/api/health

# 前端页面
curl https://你的域名.up.railway.app/
```

## 关键配置文件

### Dockerfile

```dockerfile
FROM python:3.11-slim

# 安装 Node.js
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 安装前端依赖
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm install

COPY . .

# 构建前端
RUN cd frontend && npm run build

EXPOSE 8000

CMD ["python", "backend/main.py"]
```

### railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### backend/main.py 关键改动

```python
# 静态文件挂载（前端 dist）
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")

if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA catch-all：非 API 路由全部返回 index.html"""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# 端口从环境变量读取
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
```

### frontend/vite.config.js

```javascript
export default defineConfig({
  // ...其他配置
  build: {
    outDir: 'dist',
  },
})
```

### frontend/src/api/index.js

```javascript
// baseURL 用相对路径，让 Railway 反代处理
baseURL: '/api'
```

## 常见问题排查

### 问题 1：`npm: command not found`

**现象**: Nixpacks 构建时报错 `npm: command not found`

**原因**: Nixpacks 默认不带 Node.js

**解决**: 在 `nixpacks.toml` 中添加：
```toml
[phases.setup]
nixPkgs = ["nodejs_20", "python3"]
```

> **最终方案**: 放弃 Nixpacks，改用 Dockerfile，完全控制环境。

---

### 问题 2：`undefined variable 'pip'`

**现象**: Nix 环境报 `undefined variable 'pip'`

**原因**: Nix 的 `nixPkgs` 里没有 `pip` 这个包名

**解决**: 改用 `python3 -m pip`：
```toml
[phases.build]
cmds = [
  "cd frontend && npm install && npm run build",
  "cd backend && python3 -m pip install -r requirements.txt"
]
```

> **最终方案**: Nix 的 python3 根本没有 pip 模块，必须用 Dockerfile。

---

### 问题 3：`No module named pip`

**现象**: `python3 -m pip` 报 `/root/.nix-profile/bin/python3: No module named pip`

**原因**: Nix 安装的 python3 是精简版，不含 pip

**解决**: **改用 Dockerfile**（基于 `python:3.11-slim`，自带 pip）

---

### 问题 4：Dockerfile 构建成功但部署失败

**现象**: Docker image 构建并推送成功，但 Railway 显示 Failed

**可能原因**:
1. `healthcheckPath` 配置导致健康检查超时
2. `startCommand` 与 Dockerfile CMD 冲突

**解决**: 简化 `railway.json`，移除 healthcheck 和 startCommand：
```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

---

### 问题 5：Nixpacks buildCommand 与 railway.json 冲突

**现象**: 修改了 `nixpacks.toml` 但构建仍用旧命令

**原因**: `railway.json` 的 `buildCommand` 会覆盖 `nixpacks.toml` 的 build phase

**解决**: 两者只能保留一个。用 Dockerfile 方案时不需要 `nixpacks.toml`。

---

### 问题 6：前端页面 404

**现象**: API 正常但前端页面返回 404

**原因**: FastAPI 没有挂载静态文件，或 SPA catch-all 路由缺失

**解决**: 在 `main.py` 中添加：
1. `app.mount("/assets", StaticFiles(...))` 挂载前端资源
2. `@app.get("/{full_path:path}")` catch-all 路由返回 `index.html`

---

### 问题 7：CORS 错误

**现象**: 前端调 API 时跨域报错

**解决**: 在 `main.py` 中添加 CORS 中间件：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 问题 8：Windows 环境下 git push 失败

**现象**: 本机无法通过 HTTPS 连接 github.com:443

**解决**: 使用 GitHub Contents API 推送文件：
```javascript
// 通过 Node.js 调用 GitHub API
const https = require('https');
// PUT /repos/{owner}/{repo}/contents/{path}
```

> 这是临时方案。正常环境直接 `git push` 即可。

### 问题 9：注册/登录报 500 错误 — `passlib` + `bcrypt` 版本不兼容

**现象**: 注册或登录时返回 500 Internal Server Error，日志报错：
```
AttributeError: module 'bcrypt' has no attribute '__about__'
ValueError: password cannot be longer than 72 bytes
```

**原因**: `passlib` 1.7.4 不兼容 `bcrypt>=4.1`。Dockerfile 中 `pip install` 不锁版本会装到最新 `bcrypt`5.0。

**解决**: 锁定版本：
```txt
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```

---

## 环境变量清单

| 变量 | 必需 | 说明 |
|------|------|------|
| `PORT` | 自动 | Railway 自动注入，无需手动设置 |
| `SECRET_KEY` | ✅ | JWT 签名密钥，随意生成一个长字符串 |

## 回滚

如果部署出问题：

```bash
# 查看历史部署
railway deployment list

# 回滚到上一个版本
railway deployment rollback
```

## 成本

Railway 免费层：每月 $5 额度，足够个人项目使用。

---

*最后更新: 2026-07-27*
