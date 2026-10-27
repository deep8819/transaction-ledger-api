from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["credit", "debit"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None
    reference_id: str = Field(min_length=1)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    type: str
    amount: Decimal
    description: str | None
    reference_id: str
    created_at: datetime


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    page: int
    page_size: int
    total_records: int
    total_pages: int
