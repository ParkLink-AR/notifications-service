import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import text

from app.trusted_caller import TrustedCallerMiddleware
from app import models  # noqa: F401  -- registers models on Base before create_all
from app.api.inbox import internal_router as internal_inbox_router
from app.api.inbox import router as inbox_router
from app.api.tokens import internal_router as internal_tokens_router
from app.api.tokens import router as tokens_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.logger import setup_logger
from app.messaging.consumer import Consumer
from app.services import push

setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No migrations -- same approach as auth-service. create_all is a no-op on
    # tables that already exist.
    Base.metadata.create_all(bind=engine)
    push.init_firebase()

    consumer_task = None
    if settings.CONSUMER_ENABLED:
        consumer = Consumer()
        consumer_task = asyncio.create_task(consumer.run())
        app.state.consumer = consumer
    else:
        logger.info("[STARTUP] consumer disabled (CONSUMER_ENABLED=false)")

    logger.info("[STARTUP] ParkLink Notifications Service iniciado")
    yield

    if consumer_task is not None:
        await app.state.consumer.stop()
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("[SHUTDOWN] ParkLink Notifications Service detenido")


app = FastAPI(title="ParkLink Notifications Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(TrustedCallerMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tokens_router)
app.include_router(internal_tokens_router)
app.include_router(inbox_router)
app.include_router(internal_inbox_router)


@app.get("/livez", tags=["health"])
def livez():
    """El proceso HTTP está vivo y puede recibir requests."""
    return {"status": "alive"}


@app.get("/readyz", tags=["health"])
def readyz():
    """El servicio puede operar: verifica conectividad con la base de datos."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "type": "about:blank",
                "title": "Service Unavailable",
                "status": 503,
                "detail": "Database connection failed",
                "instance": "/readyz",
            },
            media_type="application/problem+json",
        )
    finally:
        db.close()


@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "consumer_enabled": settings.CONSUMER_ENABLED,
        "firebase": "enabled" if push._is_enabled() else "log-only",
    }
