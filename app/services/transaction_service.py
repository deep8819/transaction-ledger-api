from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AccountNotFound, DuplicateTransaction, InsufficientFunds
from app.models.account import Account
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionListResponse


def create_transaction(
    db: Session, account_id: str, data: TransactionCreate
) -> Transaction:
    try:
        # A harmless write that takes SQLite's write lock first, so no other
        # request can change this balance between our check and our update.
        # It also tells us whether the account exists.
        locked = db.execute(
            update(Account).where(Account.id == account_id).values(balance=Account.balance)
        )
        if locked.rowcount == 0:
            raise AccountNotFound()

        already_used = db.execute(
            select(Transaction.id).where(
                Transaction.account_id == account_id,
                Transaction.reference_id == data.reference_id,
            )
        ).first()
        if already_used:
            raise DuplicateTransaction()

        account = db.execute(
            select(Account).where(Account.id == account_id)
        ).scalar_one()

        if data.type == "credit":
            account.balance += data.amount
        else:
            if data.amount > account.balance:
                raise InsufficientFunds()
            account.balance -= data.amount

        transaction = Transaction(
            account_id=account_id,
            type=data.type,
            amount=data.amount,
            description=data.description,
            reference_id=data.reference_id,
        )
        db.add(transaction)

        # One commit saves the new transaction AND the new balance together.
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # The database's own UNIQUE rule fired (safety net for identical
        # requests arriving at the same moment).
        if "UNIQUE constraint failed" in str(exc.orig):
            raise DuplicateTransaction() from exc
        raise
    except Exception:
        # Any failure undoes everything done above.
        db.rollback()
        raise

    db.refresh(transaction)
    return transaction


def list_transactions(
    db: Session, account_id: str, type_: str | None, page: int, limit: int
) -> TransactionListResponse:
    # Read-only: no commit, nothing is written.
    if db.get(Account, account_id) is None:
        raise AccountNotFound()

    filters = [Transaction.account_id == account_id]
    if type_ is not None:
        filters.append(Transaction.type == type_)

    total_records = db.execute(
        select(func.count()).select_from(Transaction).where(*filters)
    ).scalar_one()

    offset = (page - 1) * limit
    rows = []
    # Skipping the query for a page past the end also avoids an absurdly
    # large OFFSET that SQLite cannot handle.
    if offset < total_records:
        rows = (
            db.execute(
                select(Transaction)
                .where(*filters)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )

    return TransactionListResponse(
        transactions=rows,
        page=page,
        page_size=limit,
        total_records=total_records,
        total_pages=(total_records + limit - 1) // limit,
    )
