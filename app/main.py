from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Payment Processing Service", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(payments_router)
