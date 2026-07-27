from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/api/statistics", tags=["statistics"])

INCOME_CATEGORIES = ["工资", "奖金", "兼职", "投资收益", "红包"]
EXPENSE_CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "房租", "水电", "医疗", "教育"]


def _to_float(val) -> float:
    if isinstance(val, Decimal):
        return float(val)
    return float(val) if val is not None else 0.0


@router.get("/monthly", response_model=dict)
async def get_monthly_stats(
    year_month: str = Query("当前月份，格式 YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    async with get_db() as db:
        income_cursor = await db.execute(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions WHERE user_id = ? AND type = 'income'
               AND strftime('%Y-%m', date) = ?""",
            (current_user["id"], year_month),
        )
        income_row = await income_cursor.fetchone()
        total_income = _to_float(income_row["total"])

        expense_cursor = await db.execute(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions WHERE user_id = ? AND type = 'expense'
               AND strftime('%Y-%m', date) = ?""",
            (current_user["id"], year_month),
        )
        expense_row = await expense_cursor.fetchone()
        total_expense = _to_float(expense_row["total"])

        return {
            "monthlyStats": {
                "totalIncome": total_income,
                "totalExpense": total_expense,
                "balance": total_income - total_expense,
            }
        }


@router.get("/category-breakdown", response_model=dict)
async def get_category_breakdown(
    year_month: str = Query("当前月份，格式 YYYY-MM"),
    txn_type: str = Query("expense", regex="^(income|expense)$"),
    current_user: dict = Depends(get_current_user),
):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT category, SUM(amount) as total
               FROM transactions
               WHERE user_id = ? AND type = ? AND strftime('%Y-%m', date) = ?
               GROUP BY category
               ORDER BY total DESC""",
            (current_user["id"], txn_type, year_month),
        )
        rows = await cursor.fetchall()
        total = sum(_to_float(r["total"]) for r in rows)

        category_stats = []
        for r in rows:
            amt = _to_float(r["total"])
            pct = round((amt / total * 100), 1) if total > 0 else 0.0
            category_stats.append({
                "category": r["category"],
                "amount": amt,
                "percentage": pct,
            })

        return {"categoryStats": category_stats}


@router.get("/trend", response_model=dict)
async def get_trend_data(
    current_user: dict = Depends(get_current_user),
):
    months = []
    for i in range(6, 0, -1):
        m = (datetime.now().month - i) % 12 + 1
        y = datetime.now().year + (datetime.now().month - i) // 12
        months.append(f"{y}-{m:02d}")

    async with get_db() as db:
        trend_data = []
        for ym in months:
            inc_cursor = await db.execute(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions WHERE user_id = ? AND type = 'income'
                   AND strftime('%Y-%m', date) = ?""",
                (current_user["id"], ym),
            )
            exp_cursor = await db.execute(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions WHERE user_id = ? AND type = 'expense'
                   AND strftime('%Y-%m', date) = ?""",
                (current_user["id"], ym),
            )

            inc = _to_float((await inc_cursor.fetchone())["total"])
            exp = _to_float((await exp_cursor.fetchone())["total"])

            trend_data.append({
                "month": ym,
                "income": inc,
                "expense": exp,
            })

        monthly_stats_cursor = await db.execute(
            """SELECT
                  COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) as total_income,
                  COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as total_expense
               FROM transactions WHERE user_id = ?""",
            (current_user["id"],),
        )
        ms = await monthly_stats_cursor.fetchone()

        cat_cursor = await db.execute(
            """SELECT category, SUM(amount) as total
               FROM transactions
               WHERE user_id = ? AND type = 'expense'
               GROUP BY category ORDER BY total DESC
               LIMIT 10""",
            (current_user["id"],),
        )
        cat_rows = await cat_cursor.fetchall()
        total_exp_all = sum(_to_float(r["total"]) for r in cat_rows)

        category_stats = []
        for r in cat_rows:
            amt = _to_float(r["total"])
            pct = round((amt / total_exp_all * 100), 1) if total_exp_all > 0 else 0.0
            category_stats.append({
                "category": r["category"],
                "amount": amt,
                "percentage": pct,
            })

        return {
            "trendData": trend_data,
            "categoryStats": category_stats,
            "monthlyStats": {
                "totalIncome": _to_float(ms["total_income"]),
                "totalExpense": _to_float(ms["total_expense"]),
                "balance": _to_float(ms["total_income"]) - _to_float(ms["total_expense"]),
            },
        }
