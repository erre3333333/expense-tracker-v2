import os
import json
import asyncio
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai-analysis"])

# AI 大模型配置（Agnes AI 免费层）
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
# 工具逻辑（纯函数，不依赖 crewai）
# ============================================================

def _category_stats(data_json: str) -> str:
    """统计各分类消费占比"""
    try:
        data = json.loads(data_json)
        expense_by_category = data.get("expense_by_category", {})
        total = sum(expense_by_category.values())

        result = []
        for cat, amt in sorted(expense_by_category.items(), key=lambda x: -x[1]):
            pct = round((amt / total * 100), 1) if total > 0 else 0
            result.append({"category": cat, "amount": amt, "percentage": pct})

        return json.dumps({
            "total_expense": total,
            "categories": result,
            "top_category": result[0]["category"] if result else "无",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _inflation_estimator(data_json: str) -> str:
    """估算各类别通胀影响"""
    try:
        data = json.loads(data_json)
        history = data.get("history", [])

        if len(history) < 2:
            return json.dumps({"message": "历史数据不足，无法估算趋势"})

        recent_expenses = [h["expense"] for h in history if h["expense"] > 0]
        if len(recent_expenses) < 2:
            return json.dumps({"message": "有效消费数据不足"})

        changes = []
        for i in range(1, len(recent_expenses)):
            if recent_expenses[i - 1] > 0:
                change = (recent_expenses[i] - recent_expenses[i - 1]) / recent_expenses[i - 1]
                changes.append(change)

        avg_change = sum(changes) / len(changes) if changes else 0

        if avg_change > 0.05:
            trend = "上升"
        elif avg_change < -0.05:
            trend = "下降"
        else:
            trend = "稳定"

        return json.dumps({
            "trend": trend,
            "avg_monthly_change": round(avg_change * 100, 2),
            "recent_expenses": recent_expenses,
            "suggestion": f"消费整体{trend}，建议{'控制支出' if avg_change > 0 else '保持当前消费习惯'}",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _spending_pattern(data_json: str) -> str:
    """分析消费模式"""
    try:
        data = json.loads(data_json)
        transactions = data.get("recent_transactions", [])

        if not transactions:
            return json.dumps({"message": "无交易数据"})

        daily = {}
        for t in transactions:
            day = t["date"][:10]
            daily[day] = daily.get(day, 0) + t["amount"]

        peak_days = sorted(daily.items(), key=lambda x: -x[1])[:3]

        amounts = [t["amount"] for t in transactions]
        avg = sum(amounts) / len(amounts) if amounts else 0
        large_transactions = [t for t in transactions if t["amount"] > avg * 2]

        freq = {}
        for t in transactions:
            cat = t["category"]
            freq[cat] = freq.get(cat, 0) + 1
        frequent_cats = sorted(freq.items(), key=lambda x: -x[1])[:3]

        return json.dumps({
            "avg_daily_spending": round(avg, 2),
            "peak_days": [{"date": d, "amount": round(a, 2)} for d, a in peak_days],
            "large_transactions": [
                {"date": t["date"], "category": t["category"], "amount": t["amount"], "note": t["note"]}
                for t in large_transactions[:5]
            ],
            "frequent_categories": [{"category": c, "count": n} for c, n in frequent_cats],
            "total_transactions": len(transactions),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# Agent 构建（延迟导入 crewai）
# ============================================================

def _build_agents_and_crew(data_summary: str, year_month: str, api_key: str = ""):
    """构建 CrewAI agents 和 crew"""
    from crewai import Agent, Task, Crew, Process, LLM
    from crewai.tools import BaseTool

    # 基于纯函数创建 CrewAI 工具类
    class CategoryStatsTool(BaseTool):
        name: str = "category_stats"
        description: str = "统计各消费分类的金额和占比，返回 JSON 格式"

        def _run(self, data_json: str) -> str:
            return _category_stats(data_json)

    class InflationEstimatorTool(BaseTool):
        name: str = "inflation_estimator"
        description: str = "根据历史数据估算各类别的消费变化趋势"

        def _run(self, data_json: str) -> str:
            return _inflation_estimator(data_json)

    class SpendingPatternTool(BaseTool):
        name: str = "spending_pattern"
        description: str = "分析用户的消费模式，包括高频消费、大额消费"

        def _run(self, data_json: str) -> str:
            return _spending_pattern(data_json)

    # 初始化 LLM
    llm = LLM(
        model=DEFAULT_MODEL,
        temperature=0.3,
        api_key=api_key or AGNES_API_KEY,
        base_url=AGNES_BASE_URL,
    )

    # 实例化工具
    category_tool = CategoryStatsTool()
    inflation_tool = InflationEstimatorTool()
    pattern_tool = SpendingPatternTool()

    # Agent 1: 趋势分析师
    trend_analyst = Agent(
        role="消费趋势分析师",
        goal="分析用户的消费趋势，识别消费模式和变化方向",
        backstory="你是一位专业的消费趋势分析师，擅长从数据中发现消费模式和趋势变化。"
                  "你可以使用工具来获取更精确的统计数据。",
        verbose=False,
        allow_delegation=True,
        llm=llm,
        tools=[category_tool, inflation_tool, pattern_tool],
    )

    # Agent 2: 异常检测专家
    anomaly_detector = Agent(
        role="消费异常检测专家",
        goal="检测异常消费行为，识别不合理的支出",
        backstory="你是一位财务风控专家，擅长发现异常消费模式和潜在的财务风险。"
                  "你可以使用工具来分析消费模式。",
        verbose=False,
        allow_delegation=True,
        llm=llm,
        tools=[pattern_tool, category_tool],
    )

    # Agent 3: 预算顾问
    budget_advisor = Agent(
        role="个人预算顾问",
        goal="提供预算管理建议，帮助用户合理分配资金",
        backstory="你是一位资深的个人理财顾问，擅长制定切实可行的预算方案。"
                  "你可以使用工具来获取精确的分类统计数据。",
        verbose=False,
        allow_delegation=True,
        llm=llm,
        tools=[category_tool, inflation_tool],
    )

    # Agent 4: 省钱教练
    savings_coach = Agent(
        role="省钱教练",
        goal="提供具体的省钱建议，帮助用户减少不必要的开支",
        backstory="你是一位实用的省钱专家，总能找到既不影响生活质量又能节省开支的方法。"
                  "你可以使用工具来分析消费模式和趋势。",
        verbose=False,
        allow_delegation=True,
        llm=llm,
        tools=[category_tool, pattern_tool],
    )

    # Task 1: 趋势分析
    trend_task = Task(
        description=f"""基于以下 {year_month} 月的消费数据，分析用户的消费趋势：

{data_summary}

请使用工具获取精确的统计数据，然后分析：
1. 消费总额和收入对比
2. 主要消费类别分布
3. 消费趋势（是否有增长/下降趋势）
4. 消费习惯特点

输出格式（JSON）：
{{
  "summary": "整体消费概述",
  "trend": "上升/下降/稳定",
  "key_findings": ["发现1", "发现2", "发现3"]
}}""",
        expected_output="JSON格式的消费趋势分析报告",
        agent=trend_analyst,
    )

    # Task 2: 异常检测
    anomaly_task = Task(
        description=f"""基于以下 {year_month} 月的消费数据，检测异常消费：

{data_summary}

请使用 spending_pattern 工具分析消费模式，然后检测：
1. 单笔大额消费（超过月均消费2倍）
2. 频繁小额消费（可能的冲动消费）
3. 非常规类别消费
4. 消费时间异常

输出格式（JSON）：
{{
  "anomalies": [
    {{"type": "大额消费", "description": "描述", "amount": 金额, "suggestion": "建议"}}
  ],
  "risk_level": "低/中/高",
  "total_anomaly_amount": 总异常金额
}}""",
        expected_output="JSON格式的异常检测报告",
        agent=anomaly_detector,
    )

    # Task 3: 预算建议
    budget_task = Task(
        description=f"""基于以下 {year_month} 月的消费数据，提供预算建议：

{data_summary}

请使用 category_stats 工具获取分类统计，然后提供：
1. 各类别建议预算比例
2. 当前预算执行情况
3. 需要调整的类别
4. 下月预算建议

输出格式（JSON）：
{{
  "budget_assessment": "预算执行评估",
  "adjustments": [
    {{"category": "类别", "current": 当前金额, "suggested": 建议金额, "reason": "原因"}}
  ],
  "next_month_budget": 建议总预算
}}""",
        expected_output="JSON格式的预算建议报告",
        agent=budget_advisor,
    )

    # Task 4: 省钱建议
    savings_task = Task(
        description=f"""基于以下 {year_month} 月的消费数据，提供省钱建议：

{data_summary}

请使用 spending_pattern 工具分析消费模式，然后提供：
1. 可节省的消费领域
2. 具体的省钱方法
3. 预计可节省金额
4. 生活质量影响评估

输出格式（JSON）：
{{
  "tips": [
    {{"area": "领域", "method": "方法", "estimated_saving": 预计节省, "impact": "影响程度"}}
  ],
  "total_potential_saving": 总预计节省
}}""",
        expected_output="JSON格式的省钱建议报告",
        agent=savings_coach,
    )

    # 创建 Crew（层级模式 + 记忆）
    crew = Crew(
        agents=[trend_analyst, anomaly_detector, budget_advisor, savings_coach],
        tasks=[trend_task, anomaly_task, budget_task, savings_task],
        process=Process.hierarchical,
        memory=True,
        verbose=False,
    )

    return crew


# ============================================================
# 数据获取
# ============================================================

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
        txn = {
            "type": row["type"],
            "category": row["category"],
            "amount": amt,
            "note": row["note"] or "",
            "date": row["date"],
        }
        transactions.append(txn)
        if row["type"] == "income":
            total_income += amt
        else:
            total_expense += amt

    expense_by_category = {}
    for t in transactions:
        if t["type"] == "expense":
            cat = t["category"]
            expense_by_category[cat] = expense_by_category.get(cat, 0) + t["amount"]

    history = []
    for row in trend_rows:
        history.append({
            "month": row["month"],
            "expense": _to_float(row["expense"]),
            "income": _to_float(row["income"]),
        })

    summary = {
        "year_month": year_month,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "transaction_count": len(transactions),
        "expense_by_category": {k: round(v, 2) for k, v in expense_by_category.items()},
        "recent_transactions": transactions[:20],
        "history": history,
    }

    return summary


# ============================================================
# API 路由
# ============================================================

@router.post("/analyze")
async def analyze_expenses(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
    api_key: str = None,
):
    """多 Agent 消费分析（同步模式）"""
    api_key = api_key or AGNES_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="请先设置 API Key")

    try:
        data = await _fetch_user_data(current_user["id"], request.year_month)

        if data["transaction_count"] == 0:
            return {
                "success": False,
                "message": f"{request.year_month} 暂无交易数据，请先添加一些记录",
            }

        data_summary = json.dumps(data, ensure_ascii=False, indent=2)
        crew = _build_agents_and_crew(data_summary, request.year_month, api_key=api_key)
        result = crew.kickoff()

        analysis = {"trend": None, "anomaly": None, "budget": None, "savings": None}

        tasks_output = result.tasks_output if hasattr(result, 'tasks_output') else []
        for i, task_output in enumerate(tasks_output):
            raw = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    key = ["trend", "anomaly", "budget", "savings"][i]
                    analysis[key] = parsed
            except (json.JSONDecodeError, IndexError):
                key = ["trend", "anomaly", "budget", "savings"][i]
                analysis[key] = {"raw_text": raw}

        return {
            "success": True,
            "year_month": request.year_month,
            "analysis": analysis,
            "data_summary": {
                "total_income": data["total_income"],
                "total_expense": data["total_expense"],
                "balance": data["balance"],
            },
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

        await websocket.send_json({"type": "progress", "agent": "数据获取", "status": "正在从数据库读取消费记录..."})

        user_data = await _fetch_user_data(user_id, year_month)

        if user_data["transaction_count"] == 0:
            await websocket.send_json({"type": "error", "message": f"{year_month} 暂无交易数据"})
            await websocket.close()
            return

        await websocket.send_json({"type": "progress", "agent": "数据获取", "status": f"已获取 {user_data['transaction_count']} 条交易记录"})

        data_summary = json.dumps(user_data, ensure_ascii=False, indent=2)
        crew = _build_agents_and_crew(data_summary, year_month, api_key=api_key)

        agent_names = ["趋势分析师", "异常检测专家", "预算顾问", "省钱教练"]
        for name in agent_names:
            await websocket.send_json({"type": "agent_start", "agent": name, "status": f"{name} 已就绪，等待任务分配..."})

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, crew.kickoff)

        await websocket.send_json({"type": "progress", "agent": "Manager", "status": "所有 Agent 分析完成，正在汇总结果..."})

        analysis = {"trend": None, "anomaly": None, "budget": None, "savings": None}

        tasks_output = result.tasks_output if hasattr(result, 'tasks_output') else []
        for i, task_output in enumerate(tasks_output):
            raw = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    key = ["trend", "anomaly", "budget", "savings"][i]
                    analysis[key] = parsed
            except (json.JSONDecodeError, IndexError):
                key = ["trend", "anomaly", "budget", "savings"][i]
                analysis[key] = {"raw_text": raw}

            await websocket.send_json({"type": "agent_complete", "agent": agent_names[i], "status": f"{agent_names[i]} 分析完成"})

        await websocket.send_json({
            "type": "complete",
            "success": True,
            "year_month": year_month,
            "analysis": analysis,
            "data_summary": {
                "total_income": user_data["total_income"],
                "total_expense": user_data["total_expense"],
                "balance": user_data["balance"],
            },
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
