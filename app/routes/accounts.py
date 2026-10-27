from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import error_responses
from app.schemas.account import AccountCreate, AccountResponse, BalanceResponse
from app.services import account_service

router = APIRouter()


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(422),
)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    return account_service.create_account(db, payload)


@router.get(
    "/accounts/{account_id}/balance",
    response_model=BalanceResponse,
    responses=error_responses(404, 422),
)
def get_balance(account_id: str, db: Session = Depends(get_db)):
    return account_service.get_balance(db, account_id)
