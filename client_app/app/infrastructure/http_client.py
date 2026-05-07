# C:\Users\Mariana Ionela\MATERII\AN 4 - UTCN\LICENTA - PYTHON\client_app\app\infrastructure\http_client.py
import json as _json
import sys
import traceback

import httpx
from fastapi import HTTPException

from ..core.config import settings


# Generous timeout because Concrete FHE evaluation can be slow.
# 10 minutes total, with separate sub-timeouts so we know which phase failed.
HTTP_TIMEOUT = httpx.Timeout(
    connect=30.0,    # time to establish TCP connection
    read=600.0,      # time waiting for server to send response (10 min)
    write=600.0,     # time to send request body to server (10 min)
    pool=30.0,       # time waiting for a connection from the pool
)


def _log(msg: str) -> None:
    """Force-flush stdout so logs show up immediately in `docker compose logs`."""
    print(msg, flush=True)
    sys.stdout.flush()


async def get_from_service_provider(path: str) -> dict:
    _log(f"[GET {path}] start")
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            response = await client.get(f"{settings.service_provider_base_url}{path}")
        except httpx.HTTPError as exc:
            _log(f"[GET {path}] httpx error: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            raise HTTPException(
                status_code=502,
                detail=f"Service provider unavailable: {type(exc).__name__}: {exc}",
            ) from exc

        _log(f"[GET {path}] status={response.status_code}")

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            raise HTTPException(status_code=response.status_code, detail=detail)

        return response.json()


async def post_to_service_provider(path: str, payload: dict) -> dict:
    # Measure the payload BEFORE sending so we know what we're dealing with.
    try:
        payload_json = _json.dumps(payload)
        payload_size = len(payload_json)
        _log(
            f"[POST {path}] payload size: {payload_size} bytes "
            f"(~{payload_size / 1024:.0f} KB / {payload_size / (1024 * 1024):.2f} MB)"
        )

        # Show the structure (top-level keys + sizes), to know what's heavy.
        if isinstance(payload, dict):
            for k, v in payload.items():
                if isinstance(v, str):
                    _log(f"[POST {path}]   key='{k}' type=str len={len(v)} chars")
                elif isinstance(v, list):
                    _log(f"[POST {path}]   key='{k}' type=list len={len(v)} items")
                elif isinstance(v, dict):
                    _log(f"[POST {path}]   key='{k}' type=dict keys={list(v.keys())}")
                else:
                    _log(f"[POST {path}]   key='{k}' type={type(v).__name__} value={v!r}")
    except Exception as exc:
        _log(f"[POST {path}] failed to inspect payload: {exc}")

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            _log(f"[POST {path}] sending request (timeouts: connect=30s, read=600s, write=600s)...")
            response = await client.post(
                f"{settings.service_provider_base_url}{path}",
                json=payload,
            )
        except httpx.HTTPError as exc:
            _log(f"[POST {path}] httpx error: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            raise HTTPException(
                status_code=502,
                detail=f"Service provider unavailable: {type(exc).__name__}: {exc}",
            ) from exc
        except Exception as exc:
            _log(f"[POST {path}] UNEXPECTED error: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected client error: {type(exc).__name__}: {exc}",
            ) from exc

        _log(f"[POST {path}] response status={response.status_code}")

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            _log(f"[POST {path}] error response: {detail}")
            raise HTTPException(status_code=response.status_code, detail=detail)

        return response.json()