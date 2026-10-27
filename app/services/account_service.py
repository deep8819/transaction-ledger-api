from sqlalchemy.orm import Session

from app.errors import AccountNotFound
from app.models.account import Account
from app.schemas.account import AccountCreate, BalanceResponse


def create_account(db: Session, data: AccountCreate) -> Account:
    # Only the name comes from the client; id, balance and created_at
    # are always set by the system.
    account = Account(name=data.name, balance=0)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_balance(db: Session, account_id: str) -> BalanceResponse:
    # Read-only: no commit, nothing is written.
    account = db.get(Account, account_id)
    if account is None:
        raise AccountNotFound()
    return BalanceResponse(account_id=account.id, balance=account.balance)
