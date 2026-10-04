"""API key authentication via the Authorization header or x-api-key header."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer_scheme)
    ] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency that validates API key from Bearer token or x-api-key header.

    Supports both:
    - Authorization: Bearer <key> (OpenAI style)
    - x-api-key: <key> (Anthropic style)

    Returns the validated key on success; raises 401/403 otherwise.
    """
    # Try x-api-key header first (Anthropic style)
    if x_api_key:
        token = x_api_key
    # Fall back to Bearer token (OpenAI style)
    elif credentials:
        token = credentials.credentials
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Send it as: 'Authorization: Bearer <key>' or 'x-api-key: <key>'",
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Send it as: 'Authorization: Bearer <key>' or 'x-api-key: <key>'",
        )

    if token != settings.mock_api_key:
        logger.warning("Rejected invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return token


# Re-usable dependency shorthand
RequireAPIKey = Depends(verify_api_key)
