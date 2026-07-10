import httpx
from fastapi import HTTPException

from ..core.config import settings


HTTP_TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=600.0,
    write=600.0,
    pool=30.0,
)

async def get_from_service_provider(path: str) -> dict:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            response = await client.get(f"{settings.service_provider_base_url}{path}")
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Service provider unavailable: {type(exc).__name__}: {exc}",
            ) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            raise HTTPException(status_code=response.status_code, detail=detail)

        return response.json()


async def post_to_service_provider(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{settings.service_provider_base_url}{path}",
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Service provider unavailable: {type(exc).__name__}: {exc}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected client error: {type(exc).__name__}: {exc}",
            ) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            raise HTTPException(status_code=response.status_code, detail=detail)

        return response.json()
