from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Transaction


def test_database_rejects_transaction_for_missing_account(session_factory):
    # Insert directly through the session, bypassing the service.
    with session_factory() as db:
        db.add(
            Transaction(
                account_id="no-such-account",
                type="credit",
                amount=Decimal("1.00"),
                reference_id="r1",
            )
        )
        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            db.commit()
        db.rollback()

    with session_factory() as db:
        count = db.execute(select(func.count()).select_from(Transaction)).scalar_one()
    assert count == 0
