import os
import json
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai-analysis"])

# 智谱AI 免费层配置（GLM-4-Flash 永久免费）
ZHIPUAI_API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
DEFAULT_MODEL = "glm-4-flash"


def _to_float(val) -> float:
    if isinstance(val, Decimal):
        return float(val)
    return float(val) if val is not None else 0.0


class AnalyzeRequest(BaseModel):
    year_month: str  # YYYY-MM


def _build_agents_and_crew(data_summary: str, year_month: str, api_key: str = ""):
    """构建 CrewAI agents 和 crew"""
    from crewai import Agent, Task, Crew, Process, LLM

    # 初始化 LLM
    llm = LLM(
        model=DEFAULT_MODEL,
        temperature=0.3,
        api_key=api_key or GROQ_API_KEY,
    )

    # Agent 1: 趋势分析师
    trend_analyst = Agent(
        role="消费趋势分析师",
        goal="分析用户的消费趋势，识别消费模式和变化方向",
        backstory="你是一位专业的消费趋势分析师，擅长从数据中发现消费模式和趋势变化。",
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )

    # Agent 2: 异常检测专家
    anomaly_detector = Agent(
        role="消费异常检测专家",
        goal="检测异常消费行为，识别不合理的支出",
        backstory="你是一位财务风控专家，擅长发现异常消费模式和潜在的财务风险。",
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )

    # Agent 3: 预算顾问
    budget_advisor = Agent(
        role="个人预算顾问",
        goal="提供预算管理建议，帮助用户合理分配资金",
        backstory="你是一位资深的个人理财顾问，擅长制定切实可行的预算方案。",
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )

    # Agent 4: 省钱教练
    savings_coach = Agent(
        role="省钱教练",
        goal="提供具体的省钱建议，帮助用户减少不必要的开支",
        backstory="你是一位实用的省钱专家，总能找到既不影响生活质量又能节省开支的方法。",
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )

    # Task 1: 趋势分析
    trend_task = Task(
        description=f"""基于以下 {year_month} 月的消费数据，分析用户的消费趋势：

{data_summary}

请分析：
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

请检测：
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

请提供：
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

请提供：
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

    # 创建 Crew
    crew = Crew(
        agents=[trend_analyst, anomaly_detector, budget_advisor, savings_coach],
        tasks=[trend_task, anomaly_task, budget_task, savings_task],
        process=Process.sequential,
        verbose=False,
    )

    return crew


async def _fetch_user_data(user_id: int, year_month: str) -> dict:
    """获取用户当月的消费数据"""
    async with get_db() as db:
        # 获取当月交易
        cursor = await db.execute(
            """SELECT type, category, amount, note, date
               FROM transactions
               WHERE user_id = ? AND strftime('%Y-%m', date) = ?
               ORDER BY date""",
            (user_id, year_month),
        )
        rows = await cursor.fetchall()

        # 获取历史趋势（近6个月）
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

    # 构建数据摘要
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

    # 按类别汇总
    expense_by_category = {}
    for t in transactions:
        if t["type"] == "expense":
            cat = t["category"]
            expense_by_category[cat] = expense_by_category.get(cat, 0) + t["amount"]

    # 历史趋势
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
        "recent_transactions": transactions[:20],  # 最近20条
        "history": history,
    }

    return summary


@router.post("/analyze")
async def analyze_expenses(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
    groq_api_key: str = None,
):
    """多 Agent 消费分析"""
    api_key = groq_api_key or ZHIPUAI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="请先设置智谱AI API Key（免费获取：https://open.bigmodel.cn/）",
        )

    try:
        # 获取用户数据
        data = await _fetch_user_data(current_user["id"], request.year_month)

        if data["transaction_count"] == 0:
            return {
                "success": False,
                "message": f"{request.year_month} 暂无交易数据，请先添加一些记录",
            }

        # 构建 CrewAI
        data_summary = json.dumps(data, ensure_ascii=False, indent=2)
        crew = _build_agents_and_crew(data_summary, request.year_month, api_key=api_key)

        # 执行分析
        result = crew.kickoff()

        # 解析结果
        analysis = {
            "trend": None,
            "anomaly": None,
            "budget": None,
            "savings": None,
        }

        tasks_output = result.tasks_output if hasattr(result, 'tasks_output') else []
        for i, task_output in enumerate(tasks_output):
            raw = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
            # 尝试提取 JSON
            try:
                # 找到 JSON 部分
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    if i == 0:
                        analysis["trend"] = parsed
                    elif i == 1:
                        analysis["anomaly"] = parsed
                    elif i == 2:
                        analysis["budget"] = parsed
                    elif i == 3:
                        analysis["savings"] = parsed
            except json.JSONDecodeError:
                # JSON 解析失败，保留原始文本
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
        raise HTTPException(
            status_code=500,
            detail=f"AI 分析失败: {str(e)}",
        )
