from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.errors import register_error_handlers
from app.routes import accounts, health, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Transaction Ledger API", lifespan=lifespan)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
