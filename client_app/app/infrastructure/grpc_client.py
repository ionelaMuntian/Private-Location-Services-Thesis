# client_app/app/infrastructure/grpc_client.py

import json
import sys
import traceback
from collections.abc import AsyncIterator
from pathlib import Path

import grpc
from fastapi import HTTPException

from ..core.config import settings
from ..generated import service_provider_pb2, service_provider_pb2_grpc


GRPC_TIMEOUT_SECONDS = 600.0

# -1 means unlimited; individual scheme implementations keep their payloads sane.
GRPC_MAX_MESSAGE_SIZE = -1

# Chunk size for streaming evaluation keys (Concrete and OpenFHE SS).
# 4 MB chunks avoid building one huge gRPC message.
CONCRETE_KEY_CHUNK_SIZE = 4 * 1024 * 1024
OPENFHE_SS_KEY_CHUNK_SIZE = 4 * 1024 * 1024


def _log(msg: str) -> None:
    print(msg, flush=True)
    sys.stdout.flush()


def _target() -> str:
    return f"{settings.service_provider_grpc_host}:{settings.service_provider_grpc_port}"


def _channel_options() -> list[tuple[str, int]]:
    return [
        ("grpc.max_send_message_length", GRPC_MAX_MESSAGE_SIZE),
        ("grpc.max_receive_message_length", GRPC_MAX_MESSAGE_SIZE),
    ]


async def call_service_provider(
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict:
    """
    Generic gRPC gateway call.

    This replaces the old HTTP call from client_app to service_provider_app.
    The frontend still calls client_app through HTTP, but internal backend-to-backend
    communication uses gRPC.
    """
    payload = payload or {}

    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_size = len(payload_json)

        _log(
            f"[gRPC {method} {path}] payload size: {payload_size} bytes "
            f"(~{payload_size / 1024:.0f} KB / {payload_size / (1024 * 1024):.2f} MB)"
        )

        async with grpc.aio.insecure_channel(
            _target(),
            options=_channel_options(),
            compression=grpc.Compression.Gzip,
        ) as channel:
            stub = service_provider_pb2_grpc.ServiceProviderGatewayStub(channel)

            request = service_provider_pb2.ServiceProviderRequest(
                method=method,
                path=path,
                json_payload=payload_json,
            )

            response = await stub.Call(
                request,
                timeout=GRPC_TIMEOUT_SECONDS,
                compression=grpc.Compression.Gzip,
            )

        _log(f"[gRPC {method} {path}] status={response.status_code}")

        try:
            response_data = json.loads(response.json_payload or "{}")
        except Exception:
            response_data = {"detail": response.json_payload}

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response_data,
            )

        return response_data

    except grpc.aio.AioRpcError as exc:
        _log(f"[gRPC {method} {path}] grpc error: {exc.code()}: {exc.details()}")
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Service provider gRPC unavailable: {exc.code()}: {exc.details()}",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        _log(f"[gRPC {method} {path}] unexpected error: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected gRPC client error: {type(exc).__name__}: {exc}",
        ) from exc


async def upload_concrete_keys_to_service_provider(
    evaluation_keys_bytes: bytes,
    chunk_size: int = CONCRETE_KEY_CHUNK_SIZE,
) -> dict:
    """
    Upload Concrete evaluation keys using streaming gRPC.

    This avoids sending the evaluation keys as one huge JSON/base64 field inside
    /concrete/evaluate. That previous approach created ~700+ MB payloads and
    caused client_app to be killed with exit code 137.
    """

    async def chunk_generator() -> AsyncIterator[service_provider_pb2.ConcreteKeyChunk]:
        total_size = len(evaluation_keys_bytes)

        _log(
            f"[gRPC STREAM UploadConcreteKeys] total size: {total_size} bytes "
            f"(~{total_size / (1024 * 1024):.2f} MB), "
            f"chunk size: {chunk_size} bytes"
        )

        for start in range(0, total_size, chunk_size):
            end = min(start + chunk_size, total_size)
            yield service_provider_pb2.ConcreteKeyChunk(
                data=evaluation_keys_bytes[start:end]
            )

    try:
        async with grpc.aio.insecure_channel(
            _target(),
            options=_channel_options(),
            compression=grpc.Compression.Gzip,
        ) as channel:
            stub = service_provider_pb2_grpc.ServiceProviderGatewayStub(channel)

            response = await stub.UploadConcreteKeys(
                chunk_generator(),
                timeout=GRPC_TIMEOUT_SECONDS,
                compression=grpc.Compression.Gzip,
            )

        _log(f"[gRPC STREAM UploadConcreteKeys] status={response.status_code}")

        try:
            response_data = json.loads(response.json_payload or "{}")
        except Exception:
            response_data = {"detail": response.json_payload}

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response_data,
            )

        return response_data

    except grpc.aio.AioRpcError as exc:
        _log(
            f"[gRPC STREAM UploadConcreteKeys] grpc error: "
            f"{exc.code()}: {exc.details()}"
        )
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Concrete key upload failed: {exc.code()}: {exc.details()}",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        _log(
            f"[gRPC STREAM UploadConcreteKeys] unexpected error: "
            f"{type(exc).__name__}: {exc}"
        )
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected Concrete key upload error: {type(exc).__name__}: {exc}",
        ) from exc


async def upload_openfhe_ss_keys_from_files(
    key_files: "dict[str, str]",
    n_candidates: int,
    chunk_size: int = OPENFHE_SS_KEY_CHUNK_SIZE,
) -> dict:
    """
    Upload OpenFHE SS keys using streaming gRPC, reading from temp files on disk.

    This avoids loading all keys as base64 strings in Python memory (which caused
    client_app to be OOM-killed with exit code 137 when the payload reached ~2.8 GB).
    Each file is streamed in 4 MB chunks; files are deleted after streaming.
    """

    async def chunk_generator() -> AsyncIterator[service_provider_pb2.OpenFHESSKeyChunk]:
        yield service_provider_pb2.OpenFHESSKeyChunk(
            data=str(n_candidates).encode(),
            key_name="n_candidates",
        )
        for key_name, file_path in key_files.items():
            p = Path(file_path)
            try:
                total = p.stat().st_size
                _log(
                    f"[gRPC STREAM UploadOpenFHESSKeys] key={key_name} "
                    f"size={total} bytes (~{total / (1024 * 1024):.2f} MB)"
                )
                with open(p, "rb") as f:
                    while True:
                        data = f.read(chunk_size)
                        if not data:
                            break
                        yield service_provider_pb2.OpenFHESSKeyChunk(
                            data=data,
                            key_name=key_name,
                        )
            finally:
                p.unlink(missing_ok=True)

    try:
        async with grpc.aio.insecure_channel(
            _target(),
            options=_channel_options(),
            compression=grpc.Compression.Gzip,
        ) as channel:
            stub = service_provider_pb2_grpc.ServiceProviderGatewayStub(channel)

            response = await stub.UploadOpenFHESSKeys(
                chunk_generator(),
                timeout=GRPC_TIMEOUT_SECONDS,
                compression=grpc.Compression.Gzip,
            )

        _log(f"[gRPC STREAM UploadOpenFHESSKeys] status={response.status_code}")

        try:
            response_data = json.loads(response.json_payload or "{}")
        except Exception:
            response_data = {"detail": response.json_payload}

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response_data,
            )

        return response_data

    except grpc.aio.AioRpcError as exc:
        _log(
            f"[gRPC STREAM UploadOpenFHESSKeys] grpc error: "
            f"{exc.code()}: {exc.details()}"
        )
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"OpenFHE SS key upload failed: {exc.code()}: {exc.details()}",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        _log(
            f"[gRPC STREAM UploadOpenFHESSKeys] unexpected error: "
            f"{type(exc).__name__}: {exc}"
        )
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected OpenFHE SS key upload error: {type(exc).__name__}: {exc}",
        ) from exc


async def upload_openfhe_ss_switching_keys(
    key_id: str,
    eval_automorphism_keys_file: str,
    chunk_size: int = OPENFHE_SS_KEY_CHUNK_SIZE,
) -> dict:
    """
    Round 2 upload: sends key_id + eval automorphism keys to the server.
    The server uses them to finalise the FHEW switching key setup.
    """

    async def chunk_generator() -> AsyncIterator[service_provider_pb2.OpenFHESSKeyChunk]:
        # Signal Round 2 by sending the key_id first
        yield service_provider_pb2.OpenFHESSKeyChunk(
            data=key_id.encode(),
            key_name="key_id",
        )
        p = Path(eval_automorphism_keys_file)
        try:
            total = p.stat().st_size
            _log(
                f"[gRPC STREAM UploadOpenFHESSKeys R2] eval_automorphism_keys "
                f"size={total} bytes (~{total / (1024 * 1024):.2f} MB)"
            )
            with open(p, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield service_provider_pb2.OpenFHESSKeyChunk(
                        data=data,
                        key_name="eval_automorphism_keys",
                    )
        finally:
            p.unlink(missing_ok=True)

    try:
        async with grpc.aio.insecure_channel(
            _target(),
            options=_channel_options(),
            compression=grpc.Compression.Gzip,
        ) as channel:
            stub = service_provider_pb2_grpc.ServiceProviderGatewayStub(channel)
            response = await stub.UploadOpenFHESSKeys(
                chunk_generator(),
                timeout=GRPC_TIMEOUT_SECONDS,
                compression=grpc.Compression.Gzip,
            )

        _log(f"[gRPC STREAM UploadOpenFHESSKeys R2] status={response.status_code}")
        try:
            response_data = json.loads(response.json_payload or "{}")
        except Exception:
            response_data = {"detail": response.json_payload}

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response_data,
            )
        return response_data

    except grpc.aio.AioRpcError as exc:
        _log(f"[gRPC STREAM UploadOpenFHESSKeys R2] grpc error: {exc.code()}: {exc.details()}")
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"OpenFHE SS round-2 key upload failed: {exc.code()}: {exc.details()}",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        _log(f"[gRPC STREAM UploadOpenFHESSKeys R2] error: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"OpenFHE SS round-2 key upload error: {type(exc).__name__}: {exc}",
        ) from exc


async def get_from_service_provider(path: str) -> dict:
    return await call_service_provider("GET", path, {})


async def post_to_service_provider(path: str, payload: dict) -> dict:
    return await call_service_provider("POST", path, payload)