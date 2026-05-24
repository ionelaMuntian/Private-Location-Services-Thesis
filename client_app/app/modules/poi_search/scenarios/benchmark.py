# client_app/app/modules/poi_search/scenarios/benchmark.py

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import NearestKClientRequest
from .nearest_k import execute_nearest_k

SUPPORTED_STANDARD_SCHEMES = ["plaintext", "ckks", "concrete", "openfhe_ss"]
SUPPORTED_CONCRETE_N = [1, 5, 12, 13, 14, 15]
SUPPORTED_OPENFHE_N = [1, 5, 12, 13, 14, 15, 22, 43, 62, 122]

# Map from POI count → category that naturally has that many POIs in the dataset.
# Used for openfhe_ss N-scaling runs (each run uses the category with ~N real POIs).
_OPENFHE_N_CATEGORY = {
    1: "hospital",
    5: "school",
    12: "stationery",
    13: "post_office",
    14: "cosmetics",
    15: "gallery",
    22: "university",
    43: "hotel",
    62: "clinic",
    122: "bank",
}

_HISTORY_FILE = Path("/app/.artifacts/benchmark_history.json")
_MAX_SESSIONS = 20

def _load_history() -> list:
    try:
        if _HISTORY_FILE.exists():
            data = json.loads(_HISTORY_FILE.read_text())
            return data.get("sessions", [])
    except Exception:
        pass
    return []


def _save_session(session: dict) -> None:
    try:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        sessions = _load_history()
        sessions.insert(0, session)
        sessions = sessions[:_MAX_SESSIONS]
        _HISTORY_FILE.write_text(json.dumps({"sessions": sessions}, indent=2))
    except Exception as exc:
        print(f"[Benchmark] Warning: could not save history: {exc}", flush=True)


def _build_run_entry(scheme: str, n_candidates: int | None, result: dict) -> dict:
    metrics = result.get("metrics", {})
    client_t = metrics.get("client", {})
    server_t = metrics.get("server", {})
    workload = metrics.get("workload", {})
    sizes = result.get("sizes", {})

    if n_candidates is None:
        label = scheme
    elif scheme == "concrete":
        label = f"concrete (N={n_candidates})"
    else:
        label = f"{scheme} (N={n_candidates})"

    # Standard HE paper timing breakdown
    encrypt_ms = client_t.get("prepare_query_ms")
    upload_ms = client_t.get("upload_keys_ms")
    # candidate_fetch_ms is Concrete-specific overhead (not pure FHE)
    fetch_ms = client_t.get("candidate_fetch_ms")
    server_eval_ms = (
        server_t.get("evaluation_ms")
        or server_t.get("computation_ms")
    )
    decrypt_ms = client_t.get("parse_response_ms")
    client_total_ms = client_t.get("total_ms")
    server_total_ms = server_t.get("total_ms")

    return {
        "label": label,
        "scheme": scheme,
        "n_candidates": workload.get("candidate_count") or n_candidates,
        "result": result.get("results", [{}])[0] if result.get("results") else {},
        "timing": {
            "encrypt_ms": encrypt_ms,
            "upload_ms": upload_ms,
            "fetch_ms": fetch_ms,
            "server_eval_ms": server_eval_ms,
            "decrypt_ms": decrypt_ms,
            "client_total_ms": client_total_ms,
            "server_total_ms": server_total_ms,
            # full raw timing for backward compat
            "client": client_t,
            "server": server_t,
        },
        "sizes": {
            "ciphertext_bytes": sizes.get("ciphertext_bytes", 0),
            "key_bytes": sizes.get("key_bytes", 0),
        },
    }


def _attach_accuracy(runs: list) -> None:
    """
    Compares each run's top-1 result against the plaintext run (ground truth).

    Adds an `accuracy` dict to every run:
      top1_match        — bool: same POI ID as plaintext
      distance_error_km — absolute distance difference vs plaintext
      relative_error_pct — distance_error / plaintext_distance * 100
    For error runs or when plaintext is missing, `accuracy` is None.

    Standard HE paper metrics:
      - Top-1 accuracy: fraction of queries where the FHE result matches plaintext
      - Distance RMSE / MAE: deviation of the returned distance from true distance
      - Relative error: scheme-specific quantization / approximation error
    """
    pt = next(
        (r for r in runs
         if r.get("scheme") == "plaintext"
         and not r.get("error")
         and r.get("result")),
        None,
    )

    true_id: int | None = pt["result"].get("id") if pt else None
    true_dist: float | None = pt["result"].get("distance_km") if pt else None

    for run in runs:
        if run.get("error"):
            run["accuracy"] = None
            continue

        result = run.get("result") or {}
        pred_id = result.get("id")
        pred_dist = result.get("distance_km")

        if run.get("scheme") == "plaintext":
            run["accuracy"] = {
                "top1_match": True,
                "distance_error_km": 0.0,
                "relative_error_pct": 0.0,
            }
            continue

        acc: dict = {}
        if true_id is not None and pred_id is not None:
            acc["top1_match"] = (int(pred_id) == int(true_id))
        if true_dist is not None and pred_dist is not None and true_dist > 0:
            err = abs(float(pred_dist) - float(true_dist))
            acc["distance_error_km"] = round(err, 4)
            acc["relative_error_pct"] = round(err / float(true_dist) * 100, 2)

        run["accuracy"] = acc if acc else None


async def execute_benchmark(
    category: str,
    latitude: float,
    longitude: float,
    k: int,
    schemes: list[str],
    concrete_n_values: list[int],
    openfhe_n_values: list[int] | None = None,
) -> dict:
    runs = []

    for scheme in schemes:
        if scheme not in SUPPORTED_STANDARD_SCHEMES:
            continue

        try:
            request = NearestKClientRequest(
                category=category,
                k=k,
                latitude=latitude,
                longitude=longitude,
                scheme=scheme,
            )
            result = await execute_nearest_k(request)
            runs.append(_build_run_entry(scheme, None, result))
        except Exception as exc:
            runs.append({
                "label": scheme,
                "scheme": scheme,
                "n_candidates": None,
                "error": str(exc),
                "timing": {},
                "sizes": {},
            })

    # Explicit concrete N runs — each N maps to the category that has exactly N POIs.
    # The server always returns all POIs for a category, so the category must have
    # exactly N items for the circuit to match.
    for n in concrete_n_values:
        if n not in SUPPORTED_CONCRETE_N:
            continue
        cat = _OPENFHE_N_CATEGORY.get(n, category)
        try:
            request = NearestKClientRequest(
                category=cat,
                k=1,
                latitude=latitude,
                longitude=longitude,
                scheme="concrete",
                n_candidates=n,
            )
            result = await execute_nearest_k(request)
            runs.append(_build_run_entry("concrete", n, result))
        except Exception as exc:
            runs.append({
                "label": f"concrete (N={n})",
                "scheme": "concrete",
                "n_candidates": n,
                "error": str(exc),
                "timing": {},
                "sizes": {},
            })

    # Explicit openfhe_ss N runs — each N maps to the category that has ~N real POIs
    for n in (openfhe_n_values or []):
        if n not in SUPPORTED_OPENFHE_N:
            continue
        cat = _OPENFHE_N_CATEGORY.get(n, category)
        try:
            request = NearestKClientRequest(
                category=cat,
                k=1,
                latitude=latitude,
                longitude=longitude,
                scheme="openfhe_ss",
            )
            result = await execute_nearest_k(request)
            runs.append(_build_run_entry("openfhe_ss", n, result))
        except Exception as exc:
            runs.append({
                "label": f"openfhe_ss (N={n})",
                "scheme": "openfhe_ss",
                "n_candidates": n,
                "error": str(exc),
                "timing": {},
                "sizes": {},
            })

    _attach_accuracy(runs)

    session = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "k": k,
        "runs": runs,
    }

    _save_session(session)

    return session

async def get_benchmark_history() -> dict:
    sessions = _load_history()
    return {"sessions": sessions}
