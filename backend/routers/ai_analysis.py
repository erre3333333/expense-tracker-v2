import os
import json
import asyncio
import httpx
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai-analysis"])

# AI 大模型配置（Agnes AI 免费层，OpenAI 兼容）
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "sk-yNyarp9QLUZV8NYybNl1x8LbRPg2QzwfvsfB7iJXJ5nm971j")
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_MODEL = "agnes-2.0-flash"


def _to_float(val) -> float:
    if isinstance(val, Decimal):
        return float(val)
    return float(val) if val is not None else 0.0


class AnalyzeRequest(BaseModel):
    year_month: str  # YYYY-MM


# ============================================================
# 工具函数
# ============================================================

def _category_stats(data: dict) -> dict:
    """统计各分类消费占比"""
    expense_by_category = data.get("expense_by_category", {})
    total = sum(expense_by_category.values())
    result = []
    for cat, amt in sorted(expense_by_category.items(), key=lambda x: -x[1]):
        pct = round((amt / total * 100), 1) if total > 0 else 0
        result.append({"category": cat, "amount": amt, "percentage": pct})
    return {
        "total_expense": total,
        "categories": result,
        "top_category": result[0]["category"] if result else "无",
    }


def _inflation_estimator(data: dict) -> dict:
    """估算消费趋势"""
    history = data.get("history", [])
    if len(history) < 2:
        return {"message": "历史数据不足"}
    recent = [h["expense"] for h in history if h["expense"] > 0]
    if len(recent) < 2:
        return {"message": "有效数据不足"}
    changes = [(recent[i] - recent[i-1]) / recent[i-1] for i in range(1, len(recent)) if recent[i-1] > 0]
    avg = sum(changes) / len(changes) if changes else 0
    trend = "上升" if avg > 0.05 else ("下降" if avg < -0.05 else "稳定")
    return {"trend": trend, "avg_monthly_change": round(avg * 100, 2)}


def _spending_pattern(data: dict) -> dict:
    """分析消费模式"""
    txns = data.get("recent_transactions", [])
    if not txns:
        return {"message": "无交易数据"}
    daily = {}
    for t in txns:
        day = t["date"][:10]
        daily[day] = daily.get(day, 0) + t["amount"]
    peak = sorted(daily.items(), key=lambda x: -x[1])[:3]
    amounts = [t["amount"] for t in txns]
    avg = sum(amounts) / len(amounts) if amounts else 0
    large = [t for t in txns if t["amount"] > avg * 2]
    freq = {}
    for t in txns:
        freq[t["category"]] = freq.get(t["category"], 0) + 1
    return {
        "avg_daily_spending": round(avg, 2),
        "peak_days": [{"date": d, "amount": round(a, 2)} for d, a in peak],
        "large_transactions": [{"date": t["date"], "category": t["category"], "amount": t["amount"], "note": t["note"]} for t in large[:5]],
        "frequent_categories": sorted(freq.items(), key=lambda x: -x[1])[:3],
    }


# ============================================================
# 调用 AI API
# ============================================================

async def _call_ai(messages: list, api_key: str = "") -> str:
    """调用 Agnes AI（OpenAI 兼容接口）"""
    key = api_key or AGNES_API_KEY
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{AGNES_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": DEFAULT_MODEL, "messages": messages, "temperature": 0.3},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ============================================================
# 多 Agent 分析
# ============================================================

AGENTS = [
    {
        "name": "趋势分析师",
        "system": "你是消费趋势分析师。分析用户消费数据，输出JSON：{\"summary\":\"概述\",\"trend\":\"上升/下降/稳定\",\"key_findings\":[\"发现1\",\"发现2\",\"发现3\"]}",
        "tool": _category_stats,
    },
    {
        "name": "异常检测专家",
        "system": "你是消费异常检测专家。检测异常消费，输出JSON：{\"anomalies\":[{\"type\":\"类型\",\"description\":\"描述\",\"amount\":金额,\"suggestion\":\"建议\"}],\"risk_level\":\"低/中/高\",\"total_anomaly_amount\":总金额}",
        "tool": _spending_pattern,
    },
    {
        "name": "预算顾问",
        "system": "你是个人预算顾问。提供预算建议，输出JSON：{\"budget_assessment\":\"评估\",\"adjustments\":[{\"category\":\"类别\",\"current\":当前,\"suggested\":建议,\"reason\":\"原因\"}],\"next_month_budget\":建议总预算}",
        "tool": _category_stats,
    },
    {
        "name": "省钱教练",
        "system": "你是省钱教练。提供省钱建议，输出JSON：{\"tips\":[{\"area\":\"领域\",\"method\":\"方法\",\"estimated_saving\":预计节省,\"impact\":\"影响\"}],\"total_potential_saving\":总节省}",
        "tool": _spending_pattern,
    },
]


async def _run_agent(agent: dict, data: dict, api_key: str) -> dict:
    """运行单个 Agent"""
    tool_result = agent["tool"](data)
    messages = [
        {"role": "system", "content": agent["system"]},
        {"role": "user", "content": f"消费数据：{json.dumps(data, ensure_ascii=False)}\n\n工具分析结果：{json.dumps(tool_result, ensure_ascii=False)}\n\n请基于以上数据输出JSON分析报告。"},
    ]
    raw = await _call_ai(messages, api_key)
    # 提取 JSON
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        pass
    return {"raw_text": raw}


async def _fetch_user_data(user_id: int, year_month: str) -> dict:
    """获取用户当月的消费数据"""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT type, category, amount, note, date
               FROM transactions
               WHERE user_id = ? AND strftime('%Y-%m', date) = ?
               ORDER BY date""",
            (user_id, year_month),
        )
        rows = await cursor.fetchall()

        trend_cursor = await db.execute(
            """SELECT strftime('%Y-%m', date) as month,
                      SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense,
                      SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income
               FROM transactions
               WHERE user_id = ? AND date >= date('now', '-6 months')
               GROUP BY month ORDER BY month""",
            (user_id,),
        )
        trend_rows = await trend_cursor.fetchall()

    transactions = []
    total_income = 0
    total_expense = 0

    for row in rows:
        amt = _to_float(row["amount"])
        txn = {"type": row["type"], "category": row["category"], "amount": amt, "note": row["note"] or "", "date": row["date"]}
        transactions.append(txn)
        if row["type"] == "income":
            total_income += amt
        else:
            total_expense += amt

    expense_by_category = {}
    for t in transactions:
        if t["type"] == "expense":
            expense_by_category[t["category"]] = expense_by_category.get(t["category"], 0) + t["amount"]

    history = [{"month": r["month"], "expense": _to_float(r["expense"]), "income": _to_float(r["income"])} for r in trend_rows]

    return {
        "year_month": year_month,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "transaction_count": len(transactions),
        "expense_by_category": {k: round(v, 2) for k, v in expense_by_category.items()},
        "recent_transactions": transactions[:20],
        "history": history,
    }


# ============================================================
# API 路由
# ============================================================

@router.post("/analyze")
async def analyze_expenses(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
    api_key: str = None,
):
    """多 Agent 消费分析"""
    api_key = api_key or AGNES_API_KEY
    try:
        data = await _fetch_user_data(current_user["id"], request.year_month)

        if data["transaction_count"] == 0:
            return {"success": False, "message": f"{request.year_month} 暂无交易数据"}

        # 并行执行 4 个 Agent
        tasks = [_run_agent(agent, data, api_key) for agent in AGENTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        analysis = {"trend": None, "anomaly": None, "budget": None, "savings": None}
        keys = ["trend", "anomaly", "budget", "savings"]
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                analysis[keys[i]] = {"error": str(result)}
            else:
                analysis[keys[i]] = result

        return {
            "success": True,
            "year_month": request.year_month,
            "analysis": analysis,
            "data_summary": {"total_income": data["total_income"], "total_expense": data["total_expense"], "balance": data["balance"]},
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")


# ============================================================
# WebSocket 流式输出
# ============================================================

@router.websocket("/analyze/stream")
async def analyze_stream(websocket: WebSocket):
    """多 Agent 消费分析（WebSocket 流式模式）"""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        year_month = data.get("year_month", "")
        api_key = data.get("api_key", "") or AGNES_API_KEY
        user_id = data.get("user_id")

        if not api_key:
            await websocket.send_json({"type": "error", "message": "请先设置 Agnes AI API Key"})
            await websocket.close()
            return

        await websocket.send_json({"type": "start", "message": f"开始分析 {year_month} 消费数据..."})
        await websocket.send_json({"type": "progress", "agent": "数据获取", "status": "正在读取消费记录..."})

        user_data = await _fetch_user_data(user_id, year_month)
        if user_data["transaction_count"] == 0:
            await websocket.send_json({"type": "error", "message": f"{year_month} 暂无交易数据"})
            await websocket.close()
            return

        await websocket.send_json({"type": "progress", "agent": "数据获取", "status": f"已获取 {user_data['transaction_count']} 条记录"})

        # 逐个 Agent 执行并推送结果
        analysis = {"trend": None, "anomaly": None, "budget": None, "savings": None}
        keys = ["trend", "anomaly", "budget", "savings"]

        for i, agent in enumerate(AGENTS):
            await websocket.send_json({"type": "agent_start", "agent": agent["name"], "status": f"{agent['name']} 分析中..."})
            try:
                result = await _run_agent(agent, user_data, api_key)
                analysis[keys[i]] = result
            except Exception as e:
                analysis[keys[i]] = {"error": str(e)}
            await websocket.send_json({"type": "agent_complete", "agent": agent["name"], "status": f"{agent['name']} 完成"})

        await websocket.send_json({
            "type": "complete", "success": True, "year_month": year_month,
            "analysis": analysis,
            "data_summary": {"total_income": user_data["total_income"], "total_expense": user_data["total_expense"], "balance": user_data["balance"]},
        })
        await websocket.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": f"分析失败: {str(e)}"})
            await websocket.close()
        except:
            pass
