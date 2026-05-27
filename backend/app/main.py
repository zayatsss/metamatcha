import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import accounts, orders, triggers
from app.workers.trigger_monitor import trigger_monitor

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    trigger_monitor.start()
    yield
    await trigger_monitor.stop()


app = FastAPI(title="MetaMatcha — Multi-Account Trading Dashboard", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(orders.router)
app.include_router(triggers.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
