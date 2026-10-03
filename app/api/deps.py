from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    return idempotency_key.strip()


ApiKeyDep = Annotated[None, Depends(require_api_key)]
IdempotencyKeyDep = Annotated[str, Depends(require_idempotency_key)]
