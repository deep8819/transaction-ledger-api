from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    # Unknown fields (e.g. "balance") are rejected with a 422 error.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)


class BalanceResponse(BaseModel):
    account_id: str
    balance: Decimal


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    balance: Decimal
    created_at: datetime
