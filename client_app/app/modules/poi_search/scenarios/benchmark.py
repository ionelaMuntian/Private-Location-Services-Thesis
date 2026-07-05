import gc
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ....core.openfhe_ss_runtime import next_power_of_2 as _next_power_of_2
from ..schemas import NearestKClientRequest
from .nearest_k import execute_nearest_k

SUPPORTED_STANDARD_SCHEMES = ["plaintext", "ckks", "concrete", "openfhe_ss"]
SUPPORTED_CONCRETE_N = [1, 5, 12, 13, 14, 15]
SUPPORTED_OPENFHE_N = [1, 5, 12, 13, 14, 15, 22, 43, 62, 122]

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

    return {
        "label": label,
        "scheme": scheme,
        "n_candidates": workload.get("candidate_count") or n_candidates,
        "result": result.get("results", [{}])[0] if result.get("results") else {},
        "timing": {
            "encrypt_ms": client_t.get("prepare_query_ms"),
            "server_eval_ms": (
                server_t.get("evaluation_ms") or server_t.get("computation_ms")
            ),
            "decrypt_ms": client_t.get("parse_response_ms"),
            "client_total_ms": client_t.get("total_ms"),
        },
        "sizes": {
            "ciphertext_bytes": sizes.get("ciphertext_bytes", 0),
            "key_bytes": sizes.get("key_bytes", 0),
        },
    }


def _apply_openfhe_batch_fairness(run_entry: dict, batch_reference_encrypt_ms: dict) -> None:
    if run_entry.get("scheme") != "openfhe_ss" or run_entry.get("error"):
        return

    n_candidates = run_entry.get("n_candidates")
    if not n_candidates:
        return

    batch_size = _next_power_of_2(n_candidates)
    encrypt_ms = run_entry["timing"].get("encrypt_ms")
    reference_ms = batch_reference_encrypt_ms.get(batch_size)

    if reference_ms is None:
        if encrypt_ms is not None:
            batch_reference_encrypt_ms[batch_size] = encrypt_ms
        return

    if encrypt_ms is not None:
        run_entry["timing"]["encrypt_ms"] = round(encrypt_ms + reference_ms, 3)
    total_ms = run_entry["timing"].get("client_total_ms")
    if total_ms is not None:
        run_entry["timing"]["client_total_ms"] = round(total_ms + reference_ms, 3)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _attach_accuracy(runs: list) -> None:
    standard_pt = next(
        (r for r in runs
         if r.get("scheme") == "plaintext"
         and r.get("n_candidates") is None
         and not r.get("error")
         and r.get("result")),
        None,
    )

    n_pt_map: dict[int, dict] = {}
    for r in runs:
        n = r.get("n_candidates")
        if (r.get("scheme") == "plaintext"
                and n is not None
                and not r.get("error")
                and r.get("result")):
            n_pt_map[n] = r

    for run in runs:
        if run.get("scheme") == "plaintext":
            run["accuracy"] = {"top1_match": True, "poi_distance_km": 0.0}
            continue

        if run.get("error"):
            run["accuracy"] = None
            continue

        n = run.get("n_candidates")
        pt = n_pt_map.get(n) if n is not None else None
        if pt is None:
            pt = standard_pt

        if pt is None:
            run["accuracy"] = {}
            continue

        result = run.get("result") or {}
        pred_id = result.get("id")
        pred_lat = result.get("latitude")
        pred_lon = result.get("longitude")

        true_id = pt["result"].get("id")
        true_lat = pt["result"].get("latitude")
        true_lon = pt["result"].get("longitude")

        acc: dict = {}
        if true_id is not None and pred_id is not None:
            acc["top1_match"] = (int(pred_id) == int(true_id))

        if (true_lat is not None and true_lon is not None
                and pred_lat is not None and pred_lon is not None):
            if acc.get("top1_match"):
                acc["poi_distance_km"] = 0.0
            else:
                acc["poi_distance_km"] = round(
                    _haversine_km(true_lat, true_lon, pred_lat, pred_lon), 4
                )

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
    openfhe_batch_reference_encrypt_ms: dict[int, float] = {}

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
            run_entry = _build_run_entry(scheme, None, result)
            _apply_openfhe_batch_fairness(run_entry, openfhe_batch_reference_encrypt_ms)
            runs.append(run_entry)
        except Exception as exc:
            runs.append({
                "label": scheme,
                "scheme": scheme,
                "n_candidates": None,
                "error": str(exc),
                "timing": {},
                "sizes": {},
            })
        finally:
            gc.collect()

    _CONCRETE_MAX_RETRIES = 3
    for n in concrete_n_values:
        if n not in SUPPORTED_CONCRETE_N:
            continue
        cat = _OPENFHE_N_CATEGORY.get(n, category)
        last_exc: Exception | None = None
        for attempt in range(_CONCRETE_MAX_RETRIES):
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
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if "PBS noise" not in str(exc):
                    break
            finally:
                gc.collect()
        if last_exc is not None:
            runs.append({
                "label": f"concrete (N={n})",
                "scheme": "concrete",
                "n_candidates": n,
                "error": str(last_exc),
                "timing": {},
                "sizes": {},
            })

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
            run_entry = _build_run_entry("openfhe_ss", n, result)
            _apply_openfhe_batch_fairness(run_entry, openfhe_batch_reference_encrypt_ms)
            runs.append(run_entry)
        except Exception as exc:
            runs.append({
                "label": f"openfhe_ss (N={n})",
                "scheme": "openfhe_ss",
                "n_candidates": n,
                "error": str(exc),
                "timing": {},
                "sizes": {},
            })
        finally:
            gc.collect()

    _all_n_benchmarked: set[int] = set()
    for n in concrete_n_values:
        if n in SUPPORTED_CONCRETE_N:
            _all_n_benchmarked.add(n)
    for n in (openfhe_n_values or []):
        if n in SUPPORTED_OPENFHE_N:
            _all_n_benchmarked.add(n)

    for n in sorted(_all_n_benchmarked):
        cat = _OPENFHE_N_CATEGORY.get(n, category)
        try:
            request = NearestKClientRequest(
                category=cat,
                k=1,
                latitude=latitude,
                longitude=longitude,
                scheme="plaintext",
                n_candidates=n,
            )
            result = await execute_nearest_k(request)
            runs.append(_build_run_entry("plaintext", n, result))
        except Exception as exc:
            runs.append({
                "label": f"plaintext (N={n})",
                "scheme": "plaintext",
                "n_candidates": n,
                "error": str(exc),
                "timing": {},
                "sizes": {},
            })
        finally:
            gc.collect()

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
