import asyncio
import json as jsonlib
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def session_factory(tmp_path):
    """A throwaway SQLite file, so the real ledger.db is never touched."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


class ApiClient:
    """Minimal client that calls the FastAPI app directly (no extra library)."""

    def get(self, url):
        return self._request("GET", url)

    def post(self, url, json=None, content=None):
        if content is not None:
            body = content.encode()
        else:
            body = jsonlib.dumps(json).encode() if json is not None else b""
        return self._request("POST", url, body)

    def _request(self, method, url, body=b""):
        parts = urlsplit(url)
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": unquote(parts.path),
            "raw_path": parts.path.encode(),
            "query_string": parts.query.encode(),
            "headers": [
                (b"host", b"test"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
            "client": ("test", 0),
            "server": ("test", 80),
        }
        out = {"body": b""}
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.start":
                out["status"] = message["status"]
            elif message["type"] == "http.response.body":
                out["body"] += message.get("body", b"")

        try:
            asyncio.run(app(scope, receive, send))
        except Exception:
            # For unexpected errors Starlette sends the 500 response and then
            # re-raises so the server can log it. Only fail if no response was sent.
            if "status" not in out:
                raise
        return SimpleNamespace(
            status_code=out["status"],
            text=out["body"].decode(),
            json=lambda: jsonlib.loads(out["body"]),
        )


@pytest.fixture()
def api(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield ApiClient()
    app.dependency_overrides.clear()
