# client_app/app/modules/poi_search/scenarios/performance_simulation.py
#
# Runs a multi-point accuracy simulation against plaintext ground truth.
#
# Strategy:
#   Phase 1 — plaintext (fast, builds ground truth table)
#   Phase 2 — Concrete  (sequential, gc.collect between each)
#   Phase 3 — OpenFHE SS (sequential, gc.collect between each;
#              singleton freed at the end to release ~500 MB)
#
# All FHE calls are strictly sequential — no async concurrency inside.
#
# Estimated wall time:
#   Concrete   : 2–10 min (N=1, N=5, N=16 circuits only)
#   OpenFHE SS : ~30 min  (60 calls × ~30 s per EvalMinSchemeSwitching)
#

from __future__ import annotations

import gc
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import NearestKClientRequest
from .nearest_k import execute_nearest_k

_HISTORY_FILE = Path("/app/.artifacts/simulation_history.json")
_MAX_SESSIONS = 10

CATEGORIES = [
    "hospital",     #  1 POI  → N=1  circuit
    "school",       #  5 POIs → N=5  circuit
    "stationery",   # 12 POIs → N=12 circuit
    "post_office",  # 13 POIs → N=13 circuit
    "cosmetics",    # 14 POIs → N=14 circuit
    "gallery",      # 15 POIs → N=15 circuit
]
SCHEMES = ["concrete", "openfhe_ss"]

# 10 simulated user locations (EPSG:3857 metres) spread across the
# Cluj-Napoca dataset bounding box.
# Quantised range after ÷1000 and origin shift:
#   relative X ∈ [0, 16]  (lon_m ∈ [2_619_000, 2_635_000])
#   relative Y ∈ [0, 15]  (lat_m ∈ [5_895_000, 5_910_000])
TEST_POINTS: list[dict] = [
    {"id": 1,  "lat_m": 5_899_000.0, "lon_m": 2_621_000.0},  # SW area
    {"id": 2,  "lat_m": 5_901_000.0, "lon_m": 2_622_000.0},  # centre-S
    {"id": 3,  "lat_m": 5_902_000.0, "lon_m": 2_622_000.0},  # centre (default)
    {"id": 4,  "lat_m": 5_903_000.0, "lon_m": 2_623_000.0},  # centre
    {"id": 5,  "lat_m": 5_904_000.0, "lon_m": 2_621_000.0},  # centre-NW
    {"id": 6,  "lat_m": 5_905_000.0, "lon_m": 2_624_000.0},  # NE
    {"id": 7,  "lat_m": 5_900_000.0, "lon_m": 2_623_500.0},  # SE
    {"id": 8,  "lat_m": 5_906_000.0, "lon_m": 2_622_500.0},  # N-centre
    {"id": 9,  "lat_m": 5_897_500.0, "lon_m": 2_622_000.0},  # far S
    {"id": 10, "lat_m": 5_907_500.0, "lon_m": 2_621_000.0},  # far N
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS-84 points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _extract_top1(raw: dict) -> dict | None:
    """Pull {id, name, category, latitude, longitude, distance_km} from a nearest_k result."""
    results = raw.get("results") or []
    if not results:
        return None
    r = results[0]
    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "category": r.get("category"),
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude"),
        "distance_km": r.get("distance_km"),
    }


def _extract_timing(raw: dict) -> dict:
    """Extract standardised timing fields (matches benchmark.py convention)."""
    metrics = raw.get("metrics") or {}
    c = metrics.get("client") or {}
    s = metrics.get("server") or {}
    return {
        "encrypt_ms": c.get("prepare_query_ms"),
        "upload_ms": c.get("upload_keys_ms"),
        "fetch_ms": c.get("candidate_fetch_ms"),
        "server_eval_ms": s.get("evaluation_ms") or s.get("computation_ms"),
        "decrypt_ms": c.get("parse_response_ms"),
        "client_total_ms": c.get("total_ms"),
        "server_total_ms": s.get("total_ms"),
    }


def _compute_accuracy(predicted: dict | None, ground_truth: dict | None) -> dict:
    """
    Compute top-1 match and the geographic distance between the two returned POIs.
    poi_distance_km is the haversine distance between POI A (plaintext) and
    POI B (FHE result); 0.0 when both schemes returned the same POI.
    """
    if not predicted or not ground_truth:
        return {}

    acc: dict = {}

    if predicted.get("id") is not None and ground_truth.get("id") is not None:
        acc["top1_match"] = int(predicted["id"]) == int(ground_truth["id"])

    plat = predicted.get("latitude")
    plon = predicted.get("longitude")
    glat = ground_truth.get("latitude")
    glon = ground_truth.get("longitude")

    if plat is not None and plon is not None and glat is not None and glon is not None:
        if acc.get("top1_match"):
            acc["poi_distance_km"] = 0.0
        else:
            acc["poi_distance_km"] = round(_haversine_km(glat, glon, plat, plon), 4)

    return acc


def _build_summary(records: list[dict]) -> dict:
    """
    Aggregate accuracy metrics per scheme and per scheme×category.

    Reported metrics (standard HE evaluation):
      top1_accuracy           — fraction of queries returning the correct nearest POI
      mean_distance_error_km  — mean |d_HE − d_pt|
      max_distance_error_km   — worst-case absolute error
      rmse_distance_error_km  — √(mean(|d_HE − d_pt|²))  ← standard in papers
      mean_relative_error_pct — mean relative error (%)
    """
    def _stats(recs: list[dict]) -> dict:
        top1 = [r["accuracy"]["top1_match"] for r in recs if "top1_match" in r.get("accuracy", {})]
        d_err = [r["accuracy"]["poi_distance_km"] for r in recs if "poi_distance_km" in r.get("accuracy", {})]
        return {
            "total": len(recs),
            "top1_accuracy": round(sum(top1) / len(top1), 4) if top1 else None,
            "mean_poi_distance_km": round(sum(d_err) / len(d_err), 4) if d_err else None,
            "max_poi_distance_km": round(max(d_err), 4) if d_err else None,
            "rmse_poi_distance_km": round(math.sqrt(sum(e ** 2 for e in d_err) / len(d_err)), 4) if d_err else None,
        }

    summary: dict = {}
    for scheme in SCHEMES:
        ok_recs = [r for r in records if r["scheme"] == scheme and not r.get("error")]
        err_count = sum(1 for r in records if r["scheme"] == scheme and r.get("error"))

        per_cat: dict = {}
        for cat in CATEGORIES:
            cat_recs = [r for r in ok_recs if r["category"] == cat]
            per_cat[cat] = _stats(cat_recs)

        summary[scheme] = {
            **_stats(ok_recs),
            "error_count": err_count,
            "per_category": per_cat,
        }

    return summary


def _build_per_point(records: list[dict], ground_truths: dict) -> list[dict]:
    """Reshape flat records into the per-point structure for the frontend."""
    per_point = []
    for pt in TEST_POINTS:
        pid = pt["id"]
        categories: dict = {}
        for cat in CATEGORIES:
            gt = ground_truths.get((pid, cat))
            cat_entry: dict = {"ground_truth": gt}
            for scheme in SCHEMES:
                rec = next(
                    (r for r in records if r["point_id"] == pid and r["category"] == cat and r["scheme"] == scheme),
                    None,
                )
                if rec is None:
                    cat_entry[scheme] = None
                elif rec.get("error"):
                    cat_entry[scheme] = {"error": rec["error"]}
                else:
                    cat_entry[scheme] = {
                        "result": rec.get("result"),
                        "accuracy": rec.get("accuracy", {}),
                        "timing": rec.get("timing", {}),
                    }
            categories[cat] = cat_entry
        per_point.append({
            "point_id": pid,
            "lat_m": pt["lat_m"],
            "lon_m": pt["lon_m"],
            "categories": categories,
        })
    return per_point


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_history() -> list:
    try:
        if _HISTORY_FILE.exists():
            return json.loads(_HISTORY_FILE.read_text()).get("sessions", [])
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
        print(f"[PerfSim] Warning: could not save history: {exc}", flush=True)


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

async def execute_performance_simulation() -> dict:
    """
    Runs all (point × category × scheme) queries sequentially.

    Memory discipline:
    - Each raw result is del'd immediately after extracting the needed fields.
    - gc.collect() is called after every FHE call.
    - After all OpenFHE SS calls complete, the singleton runtime is cleared
      so the CKKS crypto context (~500 MB) is released.
    """
    total_queries = len(TEST_POINTS) * len(CATEGORIES)
    records: list[dict] = []
    ground_truths: dict = {}

    # -----------------------------------------------------------------------
    # Phase 1: plaintext — build ground-truth table
    # -----------------------------------------------------------------------
    print(
        f"[PerfSim] Phase 1/3 — plaintext ground truth ({total_queries} queries)...",
        flush=True,
    )
    for point in TEST_POINTS:
        for cat in CATEGORIES:
            pid = point["id"]
            print(f"[PerfSim]   PT {pid:2d}/10  {cat:<12s}  plaintext", flush=True)
            try:
                raw = await execute_nearest_k(NearestKClientRequest(
                    category=cat,
                    k=1,
                    latitude_m=point["lat_m"],
                    longitude_m=point["lon_m"],
                    scheme="plaintext",
                ))
                ground_truths[(pid, cat)] = _extract_top1(raw)
                del raw
            except Exception as exc:
                ground_truths[(pid, cat)] = None
                print(f"[PerfSim]   Plaintext error: {exc}", flush=True)
            finally:
                gc.collect()

    # -----------------------------------------------------------------------
    # Phase 2: Concrete FHE
    # -----------------------------------------------------------------------
    print(
        f"\n[PerfSim] Phase 2/3 — Concrete FHE ({total_queries} queries)...",
        flush=True,
    )
    for point in TEST_POINTS:
        for cat in CATEGORIES:
            pid = point["id"]
            print(f"[PerfSim]   PT {pid:2d}/10  {cat:<12s}  concrete", flush=True)
            try:
                raw = await execute_nearest_k(NearestKClientRequest(
                    category=cat,
                    k=1,
                    latitude_m=point["lat_m"],
                    longitude_m=point["lon_m"],
                    scheme="concrete",
                ))
                top1 = _extract_top1(raw)
                timing = _extract_timing(raw)
                acc = _compute_accuracy(top1, ground_truths.get((pid, cat)))
                records.append({
                    "point_id": pid,
                    "category": cat,
                    "scheme": "concrete",
                    "result": top1,
                    "accuracy": acc,
                    "timing": timing,
                })
                del raw, top1, timing, acc
            except Exception as exc:
                records.append({
                    "point_id": pid,
                    "category": cat,
                    "scheme": "concrete",
                    "error": str(exc),
                })
                print(f"[PerfSim]   Concrete error: {exc}", flush=True)
            finally:
                # Release the ConcreteClientRuntime and any circuit buffers.
                gc.collect()

    # -----------------------------------------------------------------------
    # Phase 3: OpenFHE SS
    # -----------------------------------------------------------------------
    print(
        f"\n[PerfSim] Phase 3/3 — OpenFHE SS ({total_queries} queries)...",
        flush=True,
    )
    for point in TEST_POINTS:
        for cat in CATEGORIES:
            pid = point["id"]
            print(f"[PerfSim]   PT {pid:2d}/10  {cat:<12s}  openfhe_ss", flush=True)
            try:
                raw = await execute_nearest_k(NearestKClientRequest(
                    category=cat,
                    k=1,
                    latitude_m=point["lat_m"],
                    longitude_m=point["lon_m"],
                    scheme="openfhe_ss",
                ))
                top1 = _extract_top1(raw)
                timing = _extract_timing(raw)
                acc = _compute_accuracy(top1, ground_truths.get((pid, cat)))
                records.append({
                    "point_id": pid,
                    "category": cat,
                    "scheme": "openfhe_ss",
                    "result": top1,
                    "accuracy": acc,
                    "timing": timing,
                })
                del raw, top1, timing, acc
            except Exception as exc:
                records.append({
                    "point_id": pid,
                    "category": cat,
                    "scheme": "openfhe_ss",
                    "error": str(exc),
                })
                print(f"[PerfSim]   OpenFHE SS error: {exc}", flush=True)
            finally:
                # Release intermediate serialised objects (keys, ciphertexts,
                # temp files).  The singleton CryptoContext stays alive.
                gc.collect()

    # After all OpenFHE SS calls, release the singleton (~500 MB).
    # It will be re-initialised lazily on the next openfhe_ss query.
    _clear_openfhe_ss_singleton()

    # -----------------------------------------------------------------------
    # Assemble session
    # -----------------------------------------------------------------------
    print("\n[PerfSim] Aggregating results...", flush=True)

    summary = _build_summary(records)
    per_point = _build_per_point(records, ground_truths)

    session = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_test_points": len(TEST_POINTS),
        "categories": CATEGORIES,
        "schemes": SCHEMES,
        "summary": summary,
        "per_point": per_point,
    }

    _save_session(session)

    print("[PerfSim] Done.", flush=True)
    return session


def _clear_openfhe_ss_singleton() -> None:
    """
    Null out the module-level OpenFHE SS runtime singleton so the
    CKKS crypto context and scheme-switching keys can be GC'd.
    The singleton will be lazily re-created on the next openfhe_ss query.
    """
    try:
        import client_app.app.core.openfhe_ss_runtime_instance as _mod
        if _mod._instance is not None:
            print("[PerfSim] Releasing OpenFHE SS singleton...", flush=True)
            _mod._instance = None
            gc.collect()
            print("[PerfSim] OpenFHE SS singleton released.", flush=True)
    except Exception as exc:
        print(f"[PerfSim] Warning: could not clear OpenFHE SS singleton: {exc}", flush=True)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

async def get_simulation_history() -> dict:
    return {"sessions": _load_history()}
