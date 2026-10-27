from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import error_responses
from app.schemas.transaction import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
)
from app.services import transaction_service

router = APIRouter()


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=TransactionListResponse,
    responses=error_responses(404, 422),
)
def list_transactions(
    account_id: str,
    type: Literal["credit", "debit"] | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return transaction_service.list_transactions(db, account_id, type, page, limit)


@router.post(
    "/accounts/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409, 422),
)
def create_transaction(
    account_id: str, payload: TransactionCreate, db: Session = Depends(get_db)
):
    return transaction_service.create_transaction(db, account_id, payload)
