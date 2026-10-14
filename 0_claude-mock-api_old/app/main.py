"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import verify_api_key
from app.config import settings
from app.routes.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Claude Mock API starting on %s:%s  (key=%s…)",
        settings.host,
        settings.port,
        settings.mock_api_key[:8],
    )
    yield
    logger.info("Claude Mock API shutting down")


app = FastAPI(
    title="Claude Mock API",
    description=(
        "A local API server that authenticates with a mock API key "
        "and proxies chat requests to the Claude CLI."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat_router)


# ── unauthenticated routes ──────────────────────────────────────────


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Simple health check — no auth required."""
    return {"status": "ok", "version": app.version}


# ── admin routes ────────────────────────────────────────────────────


@app.post("/admin/rotate-key", tags=["admin"])
async def rotate_api_key(
    _api_key: Annotated[str, Depends(verify_api_key)],
) -> dict:
    """Generate a new random mock API key (in-memory only).

    The caller must authenticate with the *current* key.  The response
    contains the new key — save it, because it won't be shown again.
    """
    new_key = settings.rotate_api_key()
    logger.info("API key rotated (new key=%s…)", new_key[:8])
    return {
        "message": "API key rotated successfully. Update your clients.",
        "new_api_key": new_key,
    }


# ── standalone entry point ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
