from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import InsufficientFunds
from app.models import Account, Transaction
from app.schemas.transaction import TransactionCreate
from app.services.transaction_service import create_transaction


@pytest.fixture()
def account_id(session_factory):
    with session_factory() as db:
        account = Account(name="Test", balance=Decimal("100.00"))
        db.add(account)
        db.commit()
        return account.id


def _state(session_factory, account_id):
    """Read balance and transaction count using a brand-new session."""
    with session_factory() as db:
        balance = db.get(Account, account_id).balance
        count = db.execute(select(func.count()).select_from(Transaction)).scalar_one()
    return balance, count


def test_failure_before_commit_saves_nothing(session_factory, account_id, monkeypatch):
    seen = {}

    def crash_before_commit(self):
        # Send the pending INSERT and balance UPDATE to the database (still
        # uncommitted), prove they are really there, then crash.
        self.flush()
        seen["rows_inside_transaction"] = self.execute(
            select(func.count()).select_from(Transaction)
        ).scalar_one()
        raise RuntimeError("simulated crash before commit")

    body = TransactionCreate(type="credit", amount=Decimal("50.00"), reference_id="r1")

    with session_factory() as db:
        monkeypatch.setattr(Session, "commit", crash_before_commit)
        with pytest.raises(RuntimeError, match="simulated crash"):
            create_transaction(db, account_id, body)

    assert seen["rows_inside_transaction"] == 1  # the crash really came after the add
    balance, count = _state(session_factory, account_id)
    assert balance == Decimal("100.00")
    assert count == 0


def test_rejected_debit_changes_nothing(session_factory, account_id):
    with session_factory() as db:
        create_transaction(
            db,
            account_id,
            TransactionCreate(type="credit", amount=Decimal("1.00"), reference_id="r1"),
        )
    before = _state(session_factory, account_id)
    assert before == (Decimal("101.00"), 1)

    with session_factory() as db:
        with pytest.raises(InsufficientFunds):
            create_transaction(
                db,
                account_id,
                TransactionCreate(type="debit", amount=Decimal("500"), reference_id="r2"),
            )

    assert _state(session_factory, account_id) == before
