from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import Account, Transaction

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _add_transaction(db, account_id, i, type_, created_at=None, id_=None):
    db.add(
        Transaction(
            id=id_ or f"id-{i}",
            account_id=account_id,
            type=type_,
            amount=Decimal("1.00"),
            reference_id=f"r{i}",
            created_at=created_at or BASE_TIME + timedelta(seconds=i),
        )
    )


@pytest.fixture()
def account_with_five(session_factory):
    """Five transactions r0..r4, oldest to newest: credit, debit, credit, debit, credit."""
    with session_factory() as db:
        account = Account(name="Test", balance=Decimal("0.00"))
        db.add(account)
        db.flush()
        for i in range(5):
            _add_transaction(db, account.id, i, "credit" if i % 2 == 0 else "debit")
        db.commit()
        return account.id


def _refs(response):
    return [t["reference_id"] for t in response.json()["transactions"]]


# ---- balance ----


def test_balance_after_credit_credit_debit(api):
    account_id = api.post("/accounts", json={"name": "A"}).json()["id"]
    url = f"/accounts/{account_id}/transactions"
    api.post(url, json={"type": "credit", "amount": 100, "reference_id": "a"})
    api.post(url, json={"type": "credit", "amount": 50, "reference_id": "b"})
    api.post(url, json={"type": "debit", "amount": 30, "reference_id": "c"})

    response = api.get(f"/accounts/{account_id}/balance")

    assert response.status_code == 200
    assert response.json() == {"account_id": account_id, "balance": "120.00"}


def test_balance_unknown_account_is_404(api):
    response = api.get("/accounts/nope/balance")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


# ---- history: filtering, ordering, paging ----


def test_history_unknown_account_is_404(api):
    response = api.get("/accounts/nope/transactions")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_filter_credit_only(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions?type=credit")
    body = response.json()
    assert response.status_code == 200
    assert {t["type"] for t in body["transactions"]} == {"credit"}
    assert body["total_records"] == 3


def test_filter_debit_only(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions?type=debit")
    body = response.json()
    assert {t["type"] for t in body["transactions"]} == {"debit"}
    assert body["total_records"] == 2


def test_latest_first(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions")
    assert _refs(response) == ["r4", "r3", "r2", "r1", "r0"]


def test_same_timestamp_is_ordered_by_id_descending(api, session_factory):
    with session_factory() as db:
        account = Account(name="Tie", balance=Decimal("0.00"))
        db.add(account)
        db.flush()
        for i, id_ in enumerate(["a", "c", "b"]):
            _add_transaction(db, account.id, i, "credit", BASE_TIME, id_)
        db.commit()
        account_id = account.id

    response = api.get(f"/accounts/{account_id}/transactions")

    assert [t["id"] for t in response.json()["transactions"]] == ["c", "b", "a"]


def test_page_2_limit_2_returns_correct_slice(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions?page=2&limit=2")
    body = response.json()
    assert _refs(response) == ["r2", "r1"]
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert body["total_records"] == 5


def test_total_pages_is_3_for_5_records_with_limit_2(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions?limit=2")
    assert response.json()["total_pages"] == 3


def test_page_beyond_last_is_empty_with_correct_totals(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions?page=9&limit=2")
    body = response.json()
    assert response.status_code == 200
    assert body["transactions"] == []
    assert body["total_records"] == 5
    assert body["total_pages"] == 3


def test_totals_follow_the_type_filter(api, account_with_five):
    response = api.get(
        f"/accounts/{account_with_five}/transactions?type=credit&limit=2"
    )
    body = response.json()
    assert body["total_records"] == 3
    assert body["total_pages"] == 2


def test_amounts_are_strings(api, account_with_five):
    response = api.get(f"/accounts/{account_with_five}/transactions?limit=1")
    assert response.json()["transactions"][0]["amount"] == "1.00"


# ---- history: invalid query parameters ----


@pytest.mark.parametrize(
    "query", ["type=refund", "page=0", "limit=0", "limit=101", "page=abc"]
)
def test_invalid_query_is_422(api, account_with_five, query):
    response = api.get(f"/accounts/{account_with_five}/transactions?{query}")
    assert response.status_code == 422
