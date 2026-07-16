import base64
import math
import os
from typing import cast

_LAT_REF_M = 5_891_000.0
_LON_REF_M = 2_617_000.0

# degrees are converted to meters
def _degrees_to_meters(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    lon_m = lon_deg * 20_037_508.34 / 180.0
    lat_m = math.log(math.tan(math.pi / 4.0 + math.radians(lat_deg) / 2.0)) * (20_037_508.34 / math.pi)
    return lat_m, lon_m

# strip the prefix to reduce the range
def _degrees_to_shifted_meters(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    lat_m, lon_m = _degrees_to_meters(lat_deg, lon_deg)
    return lat_m - _LAT_REF_M, lon_m - _LON_REF_M

from fastapi import HTTPException

from ....core.concrete_client_runtime import SUPPORTED_N as _CONCRETE_SUPPORTED_N
from ....core.metrics import StepTimer
from ....core.openfhe_ss_runtime import next_power_of_2 as _next_power_of_2
from ....infrastructure.grpc_client import (
    get_from_service_provider,
    post_to_service_provider,
    upload_concrete_keys_to_service_provider,
    upload_openfhe_ss_keys_from_files,
)
from ..crypto.concrete_client import ConcreteClientAdapter
from ..crypto.plaintext_client import PlaintextClientAdapter
from ..schemas import NearestKClientRequest

# helper to return the length of a base64 encoded string
def _b64len(s: str) -> int:
    try:
        return len(base64.b64decode(s)) if s else 0
    except Exception:
        return len(s) if s else 0


def _compute_payload_sizes(scheme: str, prepared: dict) -> dict:
    if scheme == "plaintext":
        return {"ciphertext_bytes": 0, "key_bytes": 0}

    enc_query = prepared.get("encrypted_query") or {}
    metadata = enc_query.get("metadata") or {}
    local_state = prepared.get("local_state") or {}

    if scheme == "concrete":
        enc_coords = metadata.get("encrypted_user_coords") or ""
        eval_keys: bytes = local_state.get("evaluation_keys_bytes") or b""
        return {
            "ciphertext_bytes": _b64len(enc_coords),
            "key_bytes": len(eval_keys),
        }

    if scheme == "openfhe_ss":
        qy = metadata.get("encrypted_qy") or ""
        qx = metadata.get("encrypted_qx") or ""
        ctx = metadata.get("crypto_context_b64") or ""
        emk = metadata.get("eval_mult_keys_b64") or ""
        return {
            "ciphertext_bytes": _b64len(qy) + _b64len(qx),
            "key_bytes": _b64len(ctx) + _b64len(emk),
        }

    return {"ciphertext_bytes": 0, "key_bytes": 0}


def get_client_adapter(scheme: str):
    if scheme == "plaintext":
        return PlaintextClientAdapter()
    if scheme == "concrete":
        return ConcreteClientAdapter()
    if scheme == "openfhe_ss":
        from ..crypto.openfhe_ss_client import OpenFHESSClientAdapter
        return OpenFHESSClientAdapter()

    raise HTTPException(status_code=400, detail=f"Unsupported scheme: {scheme}")


async def _execute_single_scheme(request: NearestKClientRequest) -> dict:
    if request.scheme == "all":
        raise HTTPException(
            status_code=400,
            detail="Internal error: _execute_single_scheme cannot run scheme=all",
        )

    # prepare the coordinates
    lat_m_full, lon_m_full = _degrees_to_meters(request.latitude, request.longitude)
    lat_m = lat_m_full - _LAT_REF_M
    lon_m = lon_m_full - _LON_REF_M

    adapter = get_client_adapter(request.scheme)

    # start the timer
    total_timer = StepTimer()

    if request.scheme == "openfhe_ss":
        count_response = await get_from_service_provider(
            f"/service/poi/category-count?category={request.category}"
        )
        actual_count = int(count_response.get("count", 0))

        if actual_count < 1:
            raise HTTPException(
                status_code=422,
                detail=f"No POIs found for category '{request.category}'.",
            )

        n_candidates = _next_power_of_2(actual_count)

        prepare_timer = StepTimer()
        prepared = adapter.prepare_query(
            latitude=lat_m,
            longitude=lon_m,
            k=request.k,
            n=n_candidates,
        )
        prepare_query_ms = prepare_timer.elapsed_ms()
        metadata = prepared["encrypted_query"]["metadata"]

        from ....core.openfhe_ss_runtime_instance import get_openfhe_ss_runtime
        rt = get_openfhe_ss_runtime(n_candidates)

        key_files = {
            "crypto_context": rt.serialize_crypto_context_to_file(),
            "public_key": rt.serialize_public_key_to_file(),
            "eval_mult_keys": rt.serialize_eval_mult_keys_to_file(),
        }
        key_bytes_size = sum(
            os.path.getsize(p) for p in key_files.values() if os.path.exists(p)
        )
        payload_sizes = {
            "ciphertext_bytes": _b64len(metadata.get("encrypted_qy", "")),
            "key_bytes": key_bytes_size,
        }

        upload_timer = StepTimer()
        key_response = await upload_openfhe_ss_keys_from_files(
            key_files=key_files,
            n_candidates=n_candidates,
        )
        upload_keys_ms = upload_timer.elapsed_ms()

        key_id = key_response.get("key_id")
        if not key_id:
            raise HTTPException(
                status_code=502,
                detail=f"OpenFHE SS key upload did not return key_id: {key_response}",
            )

        evaluate_timer = StepTimer()
        raw_response = await post_to_service_provider(
            "/service/poi/openfhe-ss/evaluate",
            {
                "key_id": key_id,
                "encrypted_qy": metadata["encrypted_qy"],
                "encrypted_qx": metadata["encrypted_qx"],
                "category": request.category,
                "n_candidates": n_candidates,
            },
        )
        evaluate_call_ms = evaluate_timer.elapsed_ms()

        parse_timer = StepTimer()
        parsed_results = adapter.parse_response(
            raw_response,
            prepared.get("local_state"),
        )
        parse_response_ms = parse_timer.elapsed_ms()

        total_ms = total_timer.elapsed_ms()
        server_metrics = raw_response.get("metrics", {})
        server_timing = server_metrics.get("server", {})
        workload = server_metrics.get("workload", {})

        return {
            "scheme": request.scheme,
            "category": request.category,
            "k": 1,
            "results": parsed_results,
            "metrics": {
                "client": {
                    "prepare_query_ms": prepare_query_ms,
                    "upload_keys_ms": upload_keys_ms,
                    "evaluate_call_ms": evaluate_call_ms,
                    "parse_response_ms": parse_response_ms,
                    "total_ms": total_ms,
                },
                "server": {
                    "candidate_selection_ms": server_timing.get("candidate_selection_ms"),
                    "computation_ms": server_timing.get("computation_ms"),
                    "argmin_ms": server_timing.get("argmin_ms"),
                    "total_ms": server_timing.get("total_ms"),
                },
                "workload": {
                    "candidate_count": workload.get("candidate_count", n_candidates),
                    "returned_count": len(parsed_results),
                    "k": 1,
                    "category": request.category,
                },
            },
            "sizes": payload_sizes,
        }

    if request.scheme == "concrete":
        if request.n_candidates is not None:
            n_candidates = request.n_candidates
        else:
            count_response = await get_from_service_provider(
                f"/service/poi/category-count?category={request.category}"
            )
            actual_count = int(count_response.get("count", 0))
            if actual_count < 1:
                raise HTTPException(
                    status_code=422,
                    detail=f"No POIs found for category '{request.category}'.",
                )
            suitable = [n for n in _CONCRETE_SUPPORTED_N if n >= actual_count]
            if not suitable:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Category '{request.category}' has {actual_count} POIs "
                        f"which exceeds the largest compiled Concrete circuit "
                        f"(N={max(_CONCRETE_SUPPORTED_N)}). Use a different scheme"
                    ),
                )
            n_candidates = min(suitable)

        # prepare the query and measure the time to do so
        prepare_timer = StepTimer()
        prepared = adapter.prepare_query(
            latitude=lat_m,
            longitude=lon_m,
            k=request.k,
            n=n_candidates,
        )
        prepare_query_ms = prepare_timer.elapsed_ms()
        payload_sizes = _compute_payload_sizes("concrete", prepared)

        local_state = prepared.get("local_state") or {}

        evaluation_keys_bytes = local_state.get("evaluation_keys_bytes")
        if evaluation_keys_bytes is None:
            raise HTTPException(
                status_code=500,
                detail="Concrete local_state is missing evaluation_keys_bytes",
            )

        # upload the keys and measure the time to do so
        upload_keys_timer = StepTimer()
        key_response = await upload_concrete_keys_to_service_provider(
            evaluation_keys_bytes=evaluation_keys_bytes,
        )
        upload_keys_ms = upload_keys_timer.elapsed_ms()

        key_id = key_response.get("key_id")
        if not key_id:
            raise HTTPException(
                status_code=502,
                detail=f"Concrete key upload did not return key_id: {key_response}",
            )

        # measure the time to send the query, evaluate it and receive it
        evaluate_call_timer = StepTimer()
        raw_response = await post_to_service_provider(
            "/service/poi/concrete/evaluate",
            {
                "key_id": key_id,
                "encrypted_user_coords_b64": prepared["encrypted_query"]["metadata"][
                    "encrypted_user_coords"
                ],
                "category": request.category,
                "requested_k": request.k,
                "n_candidates": n_candidates,
            },
        )
        evaluate_call_ms = evaluate_call_timer.elapsed_ms()

        # measure the time to parse the query
        parse_timer = StepTimer()
        parsed_results = adapter.parse_response(
            raw_response,
            local_state,
        )
        parse_response_ms = parse_timer.elapsed_ms()

        request = request.model_copy(update={"k": 1})

        total_ms = total_timer.elapsed_ms()

        evaluation_metrics = raw_response.get("metrics", {})
        evaluation_server = evaluation_metrics.get("server", {})
        evaluation_workload = evaluation_metrics.get("workload", {})

        metrics = {
            "client": {
                "prepare_query_ms": prepare_query_ms,
                "upload_keys_ms": upload_keys_ms,
                "evaluate_call_ms": evaluate_call_ms,
                "parse_response_ms": parse_response_ms,
                "total_ms": total_ms,
            },
            "server": {
                "candidate_selection_ms": evaluation_server.get(
                    "candidate_selection_ms"
                ),
                "evaluation_ms": evaluation_server.get("evaluation_ms"),
                "total_ms": evaluation_server.get("total_ms"),
            },
            "workload": {
                "candidate_count": evaluation_workload.get(
                    "candidate_count",
                    n_candidates,
                ),
                "returned_count": len(parsed_results),
                "k": request.k,
                "category": request.category,
            },
        }

        return {
            "scheme": request.scheme,
            "category": request.category,
            "k": request.k,
            "results": parsed_results,
            "metrics": metrics,
            "sizes": payload_sizes,
        }

    # if plaintext
    prepare_timer = StepTimer()
    prepared = adapter.prepare_query(
        latitude=lat_m_full if request.scheme == "plaintext" else lat_m,
        longitude=lon_m_full if request.scheme == "plaintext" else lon_m,
        k=request.k,
    )
    prepare_query_ms = prepare_timer.elapsed_ms()
    payload_sizes = _compute_payload_sizes(request.scheme, prepared)

    service_payload = {
        "category": request.category,
        "k": request.k,
        "scheme": request.scheme,
        "plaintext_query": prepared["plaintext_query"],
        "encrypted_query": prepared["encrypted_query"],
    }

    service_timer = StepTimer()
    raw_response = await post_to_service_provider(
        "/service/poi/nearest-k",
        service_payload,
    )
    service_call_ms = service_timer.elapsed_ms()

    parse_timer = StepTimer()
    parsed_results = adapter.parse_response(
        raw_response,
        prepared.get("local_state"),
    )
    parse_response_ms = parse_timer.elapsed_ms()

    total_ms = total_timer.elapsed_ms()
    server_metrics = raw_response.get("metrics", {})
    server_timing = server_metrics.get("server", {})
    workload = server_metrics.get("workload", {})

    return {
        "scheme": request.scheme,
        "category": request.category,
        "k": request.k,
        "results": parsed_results,
        "metrics": {
            "client": {
                "prepare_query_ms": prepare_query_ms,
                "service_call_ms": service_call_ms,
                "parse_response_ms": parse_response_ms,
                "total_ms": total_ms,
            },
            "server": {
                "candidate_selection_ms": server_timing.get(
                    "candidate_selection_ms"
                ),
                "computation_ms": server_timing.get("computation_ms"),
                "total_ms": server_timing.get("total_ms"),
            },
            "workload": {
                "candidate_count": workload.get("candidate_count"),
                "returned_count": len(parsed_results),
                "k": request.k,
                "category": request.category,
            },
        },
        "sizes": payload_sizes,
    }


async def execute_nearest_k(request: NearestKClientRequest) -> dict:
    if request.scheme != "all":
        return await _execute_single_scheme(request)

    runs = []

    for scheme in ["plaintext", "openfhe_ss"]:
        scheme_request = NearestKClientRequest(
            category=request.category,
            k=request.k,
            latitude=request.latitude,
            longitude=request.longitude,
            scheme=cast(str, scheme),
        )

        result = await _execute_single_scheme(scheme_request)
        runs.append(result)

    return {
        "mode": "all",
        "category": request.category,
        "k": request.k,
        "runs": runs,
    }