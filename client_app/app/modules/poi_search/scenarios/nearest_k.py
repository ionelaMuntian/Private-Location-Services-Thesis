# client_app/app/modules/poi_search/scenarios/nearest_k.py
from typing import cast

from fastapi import HTTPException

from ....core.metrics import StepTimer
from ....infrastructure.http_client import post_to_service_provider
from ..crypto.bfv_client import BFVClientAdapter
from ..crypto.ckks_client import CKKSClientAdapter
from ..crypto.concrete_client import ConcreteClientAdapter
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
    # Concrete — two-round protocol
    # Round 1: fetch all POIs in the category (no location sent).
    # Round 2: client encrypts (user_coords, poi_coords) together and asks the
    #          server to evaluate the FHE distance circuit.
    # -------------------------------------------------------------------------
    if request.scheme == "concrete":
        prepare_timer = StepTimer()
        prepared = adapter.prepare_query(
            latitude=request.latitude_m,
            longitude=request.longitude_m,
            k=request.k,
        )
        prepare_query_ms = prepare_timer.elapsed_ms()

        # Round 1 — category-only request: the server learns the category and k,
        # but NOT the user's location.
        candidate_fetch_timer = StepTimer()
        candidate_response = await post_to_service_provider(
            "/service/poi/concrete/candidates",
            {
                "category": request.category,
                "k": request.k,
                # No latitude_m / longitude_m here.
            },
        )
        candidate_fetch_ms = candidate_fetch_timer.elapsed_ms()

        # Client builds encrypted distance arguments using its PRIVATE coords
        # + the public POI coords. The server will only ever see the ciphertext.
        build_public_args_timer = StepTimer()
        items = adapter.build_public_args_for_candidates(
            prepared["encrypted_query"]["metadata"],
            candidate_response["candidates"],
            prepared["local_state"],
        )
        build_public_args_ms = build_public_args_timer.elapsed_ms()

        # Round 2 — send only evaluation keys + encrypted arguments, no plaintext coords.
        evaluate_call_timer = StepTimer()
        raw_response = await post_to_service_provider(
            "/service/poi/concrete/evaluate",
            {
                "evaluation_keys_b64": prepared["encrypted_query"]["metadata"]["evaluation_keys"],
                "requested_k": request.k,
                "items": items,
            },
        )
        evaluate_call_ms = evaluate_call_timer.elapsed_ms()

        # Client decrypts and sorts locally.
        parse_timer = StepTimer()
        parsed_results = adapter.parse_response(
            raw_response,
            prepared.get("local_state"),
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
                "candidate_fetch_ms": candidate_fetch_ms,
                "build_public_args_ms": build_public_args_ms,
                "evaluate_call_ms": evaluate_call_ms,
                "parse_response_ms": parse_response_ms,
                "total_ms": total_ms,
            },
            "server": {
                "candidate_selection_ms": candidate_server.get("candidate_selection_ms"),
                "evaluation_ms": evaluation_server.get("evaluation_ms"),
                "total_ms": server_total_ms,
            },
            "workload": {
                "candidate_count": candidate_workload.get("candidate_count", len(items)),
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
    # BFV / CKKS — single-round protocol
    # The client sends only the encrypted ciphertext + public context.
    # The server computes encrypted distances over ALL POIs in the category
    # and returns all encrypted results.
    # The client decrypts and sorts locally.
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
        # plaintext_query is None for HE schemes — never sent.
        "plaintext_query": prepared["plaintext_query"],
        "encrypted_query": prepared["encrypted_query"],
        # No latitude_m / longitude_m in metadata — see bfv_client.py / ckks_client.py.
    }

    service_timer = StepTimer()
    raw_response = await post_to_service_provider(
        "/service/poi/nearest-k",
        service_payload,
    )
    service_call_ms = service_timer.elapsed_ms()

    # Client decrypts and sorts locally.
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
                "candidate_selection_ms": server_timing.get("candidate_selection_ms"),
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
    for scheme in ["plaintext", "ckks", "bfv"]:
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