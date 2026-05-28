from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.cards import router as cards_router
from app.api.v1.findings import router as findings_router
from app.api.v1.sessions import router as sessions_router
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="PASS-PAC Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards_router, prefix="/api/v1")
app.include_router(findings_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "PASS-PAC Backend",
    }
