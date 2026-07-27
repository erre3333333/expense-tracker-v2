from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Transaction models ---

class TransactionBase(BaseModel):
    type: str = Field(..., pattern=r"^(income|expense)$")
    category: str
    amount: float = Field(..., gt=0)
    note: str = ""
    date: str


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    type: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    note: Optional[str] = None
    date: Optional[str] = None


class TransactionOut(TransactionBase):
    id: int
    user_id: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# --- Statistics models ---

class MonthlyStats(BaseModel):
    totalIncome: float
    totalExpense: float
    balance: float


class CategoryStat(BaseModel):
    category: str
    amount: float
    percentage: float


class TrendPoint(BaseModel):
    month: str
    income: float
    expense: float


class TrendData(BaseModel):
    trendData: List[TrendPoint]
    categoryStats: List[CategoryStat]
    monthlyStats: MonthlyStats
