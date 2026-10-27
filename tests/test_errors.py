import pytest

from app.services import transaction_service


@pytest.fixture()
def account_id(api):
    return api.post("/accounts", json={"name": "A"}).json()["id"]


def _tx(account_id):
    return f"/accounts/{account_id}/transactions"


def _credit(reference_id="r1", **overrides):
    return {"type": "credit", "amount": 100, "reference_id": reference_id, **overrides}


def test_account_not_found_404(api):
    response = api.get("/accounts/nope/balance")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "ACCOUNT_NOT_FOUND",
            "message": "Account not found",
            "details": [],
        }
    }


def test_account_not_found_on_create_transaction_404(api):
    response = api.post(_tx("nope"), json=_credit())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_insufficient_funds_409(api, account_id):
    api.post(_tx(account_id), json=_credit("r1"))

    response = api.post(
        _tx(account_id), json={"type": "debit", "amount": 500, "reference_id": "r2"}
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "INSUFFICIENT_FUNDS",
            "message": "Insufficient funds: debit exceeds balance",
            "details": [],
        }
    }


def test_duplicate_transaction_409(api, account_id):
    api.post(_tx(account_id), json=_credit("r1"))

    response = api.post(_tx(account_id), json=_credit("r1"))

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "DUPLICATE_TRANSACTION",
            "message": "Transaction with this reference_id already exists for this account",
            "details": [],
        }
    }


def test_validation_error_has_field_details(api, account_id):
    response = api.post(_tx(account_id), json=_credit(type="refund"))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"] == [
        {"field": "body.type", "message": "Input should be 'credit' or 'debit'"}
    ]


def test_validation_error_invalid_amount(api, account_id):
    response = api.post(_tx(account_id), json=_credit(amount=0))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in error["details"]] == ["body.amount"]


def test_validation_error_missing_fields_lists_each(api, account_id):
    response = api.post(_tx(account_id), json={})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {d["field"] for d in error["details"]} == {
        "body.type",
        "body.amount",
        "body.reference_id",
    }


@pytest.mark.parametrize(
    ("query", "field"),
    [("page=0", "query.page"), ("limit=101", "query.limit"), ("type=x", "query.type")],
)
def test_validation_error_bad_query_params(api, account_id, query, field):
    response = api.get(f"{_tx(account_id)}?{query}")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in error["details"]] == [field]
    assert all(d["message"] for d in error["details"])


def test_malformed_json_is_validation_error(api, account_id):
    response = api.post(_tx(account_id), content="{not valid json")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "body"


def test_unknown_url_uses_standard_shape(api):
    response = api.get("/no/such/page")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["details"] == []


def test_unexpected_crash_is_500_without_leaking_details(
    api, account_id, monkeypatch, caplog
):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail: C:\\private\\db.sqlite")

    monkeypatch.setattr(transaction_service, "list_transactions", boom)

    response = api.get(_tx(account_id))

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": [],
        }
    }
    for leaked in ("secret", "RuntimeError", "Traceback", "private", ".py"):
        assert leaked not in response.text
    # The real error is logged on the server instead.
    assert "secret internal detail" in caplog.text
