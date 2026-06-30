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
    "hospital",
    "school",
    "stationery",
    "post_office",
    "cosmetics",
    "gallery",
]
SCHEMES = ["concrete", "openfhe_ss"]

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

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

def _extract_top1(raw: dict) -> dict | None:
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

# Persistence
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


# Core simulation

async def execute_performance_simulation() -> dict:
    total_queries = len(TEST_POINTS) * len(CATEGORIES)
    records: list[dict] = []
    ground_truths: dict = {}

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

    _CONCRETE_MAX_RETRIES = 3

    print(
        f"\n[PerfSim] Phase 2/3 — Concrete FHE ({total_queries} queries)...",
        flush=True,
    )
    for point in TEST_POINTS:
        for cat in CATEGORIES:
            pid = point["id"]
            print(f"[PerfSim]   PT {pid:2d}/10  {cat:<12s}  concrete", flush=True)
            last_exc: Exception | None = None
            for attempt in range(_CONCRETE_MAX_RETRIES):
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
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if "PBS noise" not in str(exc):
                        break
                    print(f"[PerfSim]   Concrete PBS noise (attempt {attempt + 1}/{_CONCRETE_MAX_RETRIES}), retrying...", flush=True)
                finally:
                    gc.collect()
            if last_exc is not None:
                records.append({
                    "point_id": pid,
                    "category": cat,
                    "scheme": "concrete",
                    "error": str(last_exc),
                })
                print(f"[PerfSim]   Concrete error: {last_exc}", flush=True)

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
                gc.collect()

    _clear_openfhe_ss_singleton()

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
    try:
        import client_app.app.core.openfhe_ss_runtime_instance as _mod
        if _mod._instance is not None:
            print("[PerfSim] Releasing OpenFHE SS singleton...", flush=True)
            _mod._instance = None
            gc.collect()
            print("[PerfSim] OpenFHE SS singleton released.", flush=True)
    except Exception as exc:
        print(f"[PerfSim] Warning: could not clear OpenFHE SS singleton: {exc}", flush=True)

async def get_simulation_history() -> dict:
    return {"sessions": _load_history()}