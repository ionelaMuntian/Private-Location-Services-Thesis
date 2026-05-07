# client_app/app/modules/poi_search/scenarios/nearest_k.py

from typing import cast

from fastapi import HTTPException

from ....core.metrics import StepTimer
from ....infrastructure.grpc_client import (
    post_to_service_provider,
    upload_concrete_keys_to_service_provider,
)
from ..crypto.bfv_client import BFVClientAdapter
from ..crypto.ckks_client import CKKSClientAdapter
from ..crypto.concrete_client import ConcreteClientAdapter
from ..crypto.openfhe_client import OpenFHEClientAdapter
from ..crypto.plaintext_client import PlaintextClientAdapter
from ..schemas import NearestKClientRequest


def get_client_adapter(scheme: str):
    if scheme == "plaintext":
        return PlaintextClientAdapter()
    if scheme == "ckks":
        return CKKSClientAdapter()
    if scheme == "bfv":
        return BFVClientAdapter()
    if scheme == "concrete":
        return ConcreteClientAdapter()
    if scheme == "openfhe":
        return OpenFHEClientAdapter()

    raise HTTPException(status_code=400, detail=f"Unsupported scheme: {scheme}")


async def _execute_single_scheme(request: NearestKClientRequest) -> dict:
    if request.scheme == "all":
        raise HTTPException(
            status_code=400,
            detail="Internal error: _execute_single_scheme cannot run scheme='all'.",
        )

    adapter = get_client_adapter(request.scheme)
    total_timer = StepTimer()

    # -------------------------------------------------------------------------
    # Concrete — optimized protocol over gRPC
    #
    # Step 1: Prepare query on trusted client side.
    #         The user coordinates are encrypted once.
    #
    # Step 2: Upload Concrete evaluation keys using streaming gRPC.
    #         This avoids sending hundreds of MB inside /concrete/evaluate.
    #         The service provider returns a key_id.
    #
    # Step 3: Fetch category candidates.
    #         No user location is sent.
    #
    # Step 4: Send key_id + encrypted user coordinates + clear POI coordinates.
    #         The service provider evaluates encrypted distances.
    #
    # Step 5: Client decrypts distances and sorts locally.
    # -------------------------------------------------------------------------
    if request.scheme == "concrete":
        prepare_timer = StepTimer()
        prepared = adapter.prepare_query(
            latitude=request.latitude_m,
            longitude=request.longitude_m,
            k=request.k,
        )
        prepare_query_ms = prepare_timer.elapsed_ms()

        local_state = prepared.get("local_state") or {}

        evaluation_keys_bytes = local_state.get("evaluation_keys_bytes")
        if evaluation_keys_bytes is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Concrete local_state is missing evaluation_keys_bytes. "
                    "Check ConcreteClientAdapter.prepare_query()."
                ),
            )

        # Step 2 — upload Concrete evaluation keys through streaming gRPC.
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

        # Step 3 — category-only request: server learns the category and k,
        # but not the user's location.
        candidate_fetch_timer = StepTimer()
        candidate_response = await post_to_service_provider(
            "/service/poi/concrete/candidates",
            {
                "category": request.category,
                "k": request.k,
            },
        )
        candidate_fetch_ms = candidate_fetch_timer.elapsed_ms()

        # Step 4 preparation — build clear public POI coordinates.
        # No encryption per candidate is done here.
        build_public_args_timer = StepTimer()
        items = adapter.build_public_args_for_candidates(
            prepared["encrypted_query"]["metadata"],
            candidate_response.get("candidates", []),
            local_state,
        )
        build_public_args_ms = build_public_args_timer.elapsed_ms()

        # Step 4 — send only key_id, encrypted user coords, and POI coordinates.
        # The huge evaluation keys are no longer included in this payload.
        evaluate_call_timer = StepTimer()
        raw_response = await post_to_service_provider(
            "/service/poi/concrete/evaluate",
            {
                "key_id": key_id,
                "encrypted_user_coords_b64": prepared["encrypted_query"]["metadata"][
                    "encrypted_user_coords"
                ],
                "requested_k": request.k,
                "items": items,
            },
        )
        evaluate_call_ms = evaluate_call_timer.elapsed_ms()

        # Step 5 — client decrypts and sorts locally.
        parse_timer = StepTimer()
        parsed_results = adapter.parse_response(
            raw_response,
            local_state,
        )
        parse_response_ms = parse_timer.elapsed_ms()

        total_ms = total_timer.elapsed_ms()

        candidate_metrics = candidate_response.get("metrics", {})
        evaluation_metrics = raw_response.get("metrics", {})

        candidate_server = candidate_metrics.get("server", {})
        evaluation_server = evaluation_metrics.get("server", {})
        candidate_workload = candidate_metrics.get("workload", {})

        server_total_ms = None
        if (
            candidate_server.get("total_ms") is not None
            or evaluation_server.get("total_ms") is not None
        ):
            server_total_ms = round(
                float(candidate_server.get("total_ms", 0.0) or 0.0)
                + float(evaluation_server.get("total_ms", 0.0) or 0.0),
                3,
            )

        metrics = {
            "client": {
                "prepare_query_ms": prepare_query_ms,
                "upload_keys_ms": upload_keys_ms,
                "candidate_fetch_ms": candidate_fetch_ms,
                "build_public_args_ms": build_public_args_ms,
                "evaluate_call_ms": evaluate_call_ms,
                "parse_response_ms": parse_response_ms,
                "total_ms": total_ms,
            },
            "server": {
                "candidate_selection_ms": candidate_server.get(
                    "candidate_selection_ms"
                ),
                "evaluation_ms": evaluation_server.get("evaluation_ms"),
                "total_ms": server_total_ms,
            },
            "workload": {
                "candidate_count": candidate_workload.get(
                    "candidate_count",
                    len(items),
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
        }

    # -------------------------------------------------------------------------
    # Plaintext / BFV / CKKS / OpenFHE — single-round protocol
    # -------------------------------------------------------------------------
    prepare_timer = StepTimer()
    prepared = adapter.prepare_query(
        latitude=request.latitude_m,
        longitude=request.longitude_m,
        k=request.k,
    )
    prepare_query_ms = prepare_timer.elapsed_ms()

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
    }


async def execute_nearest_k(request: NearestKClientRequest) -> dict:
    if request.scheme != "all":
        return await _execute_single_scheme(request)

    runs = []

    # Concrete is intentionally not included in "all" because it is much heavier
    # and uses a separate multi-step protocol.
    for scheme in ["plaintext", "ckks", "bfv", "openfhe"]:
        scheme_request = NearestKClientRequest(
            category=request.category,
            k=request.k,
            latitude_m=request.latitude_m,
            longitude_m=request.longitude_m,
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