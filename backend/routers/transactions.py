from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from models.schemas import (
    TransactionCreate,
    TransactionUpdate,
    TransactionOut,
)
from routers.auth import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _format_ts(ts: Optional[str]) -> Optional[str]:
    if ts and datetime.fromisoformat(ts).tzinfo is None:
        return ts + "+00:00"
    return ts


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreate,
    current_user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO transactions (user_id, type, category, amount, note, date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (current_user["id"], body.type, body.category, body.amount, body.note, body.date, now),
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT id, user_id, type, category, amount, note, date, created_at
               FROM transactions WHERE id = last_insert_rowid()"""
        )
        tx = dict(await cursor.fetchone())
        tx["created_at"] = _format_ts(tx["created_at"])
        return tx


@router.get("", response_model=List[TransactionOut])
async def list_transactions(
    limit: int = 100,
    offset: int = 0,
    month: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    async with get_db() as db:
        if month:
            query = """SELECT id, user_id, type, category, amount, note, date, created_at
                       FROM transactions
                       WHERE user_id = ? AND strftime('%Y-%m', date) = ?
                       ORDER BY date DESC, id DESC
                       LIMIT ? OFFSET ?"""
            cursor = await db.execute(query, (current_user["id"], month, limit, offset))
        else:
            query = """SELECT id, user_id, type, category, amount, note, date, created_at
                       FROM transactions
                       WHERE user_id = ?
                       ORDER BY date DESC, id DESC
                       LIMIT ? OFFSET ?"""
            cursor = await db.execute(query, (current_user["id"], limit, offset))

        rows = [dict(r) for r in await cursor.fetchall()]
        for r in rows:
            r["created_at"] = _format_ts(r["created_at"])
        return rows


@router.get("/{tx_id}", response_model=TransactionOut)
async def get_transaction(
    tx_id: int,
    current_user: dict = Depends(get_current_user),
):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, user_id, type, category, amount, note, date, created_at
               FROM transactions WHERE id = ? AND user_id = ?""",
            (tx_id, current_user["id"]),
        )
        tx = await cursor.fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail="交易不存在")
        tx = dict(tx)
        tx["created_at"] = _format_ts(tx["created_at"])
        return tx


@router.put("/{tx_id}", response_model=TransactionOut)
async def update_transaction(
    tx_id: int,
    body: TransactionUpdate,
    current_user: dict = Depends(get_current_user),
):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM transactions WHERE id = ? AND user_id = ?",
            (tx_id, current_user["id"]),
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="交易不存在")

        fields = []
        values = []
        for field, value in body.model_dump(exclude_unset=True).items():
            fields.append(f"{field} = ?")
            values.append(value)

        if not fields:
            raise HTTPException(status_code=400, detail="没有需要更新的字段")

        values.extend([tx_id, current_user["id"]])
        await db.execute(
            f"UPDATE transactions SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            values,
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT id, user_id, type, category, amount, note, date, created_at
               FROM transactions WHERE id = ?""",
            (tx_id,),
        )
        tx = dict(await cursor.fetchone())
        tx["created_at"] = _format_ts(tx["created_at"])
        return tx


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    tx_id: int,
    current_user: dict = Depends(get_current_user),
):
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (tx_id, current_user["id"]),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="交易不存在")
