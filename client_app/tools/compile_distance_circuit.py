# client_app/tools/compile_distance_circuit.py
#
# Compiles one Concrete FHE circuit per supported N value.
# Each circuit takes encrypted user coordinates + N clear POI inputs
# and returns the ID and squared distance of the closest POI (k=1).

# Supported N values: 1, 5, 12, 13, 14, 15
# Artifacts saved to: client_app/.artifacts/concrete/
#   server_nN.zip        — loaded by the service provider
#   client_specs_nN.bin  — loaded by the client for key generation / encrypt / decrypt
#
# Compilation speed notes
# -----------------------
# Two parameters dominate compile time:
#
#   1. Inputset size — Concrete traces the circuit once per sample to infer
#      bit widths for every intermediate value.  We only need:
#        • 2 extreme-range samples (so Concrete sees the max dist² = 481 ≈ 9 bits)
#        • 1 sample per POI slot where that slot is the minimum
#             → exercises every np.where branch exactly once
#      Total: N + 2  (vs the previous ~4N + 20 + boundary = ~4.2× larger)
#
#   2. FHE parameter search — without an explicit error budget, Concrete targets
#      a near-perfect noise floor (~1e-10 per PBS) and searches a huge parameter
#      space.  For a nearest-POI circuit a global 0.01% error rate (1-in-10 000
#      circuit evaluations returns a wrong result) is completely acceptable.
#      Setting global_p_error=1e-4 lets the optimizer converge 10–100× faster.

import time
from pathlib import Path

import numpy as np
from concrete import fhe

CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_N = [1, 5, 12, 13, 14, 15]

# Cluj-Napoca dataset: after ÷2200 and reference subtraction the shifted
# coordinates fit in [0, 11] × [0, 11] (max shifted_m / 2200 ≈ 11.04).
# Max dist² = 11² + 11² = 242 (~8 bits) — PBS LUT has 256 entries.
# Same key sizes as the original 3000-scale circuits; 27% finer resolution.
COORD_MAX_X = 11
COORD_MAX_Y = 11

# p_error: probability that a SINGLE PBS operation produces a wrong output.
# Unlike global_p_error, this is circuit-size independent — the optimizer
# solves a fixed parameter search regardless of N, so compilation time is
# roughly constant across all N values.
#
# With compress_evaluation_keys=True the serialised keys are ~30–40× smaller
# than uncompressed, so we can afford tighter p_error without hitting gRPC
# transfer limits.
#
# 1e-5 per PBS → circuit error (N=5 has ~22 PBS including squarings):
#   N=5  (~22 PBS): 1 - (1-1e-5)^22 ≈ 0.022%  → ~1 in 4 500 queries fails
#   N=15 (~62 PBS): 1 - (1-1e-5)^62 ≈ 0.062%  → ~1 in 1 600 queries fails
_P_ERROR = 1e-5


# ---------------------------------------------------------------------------
# Circuit generation  (unchanged)
# ---------------------------------------------------------------------------

def _make_circuit_fn(n: int):
    """
    Dynamically builds the find-minimum circuit function for N POIs.

    Signature:
      circuit(qx_rel, qy_rel, p1x, p1y, p1_id, p2x, p2y, p2_id, ..., pNx, pNy, pN_id)

    Returns:
      (best_id, best_dist2)  — encrypted, server never decrypts these.
    """
    param_names = ["qx_rel", "qy_rel"]
    for i in range(1, n + 1):
        param_names += [f"p{i}x", f"p{i}y", f"p{i}_id"]

    lines = [f"def circuit({', '.join(param_names)}):"]
    lines.append("    encrypted_zero = qx_rel - qx_rel")

    # Distance to first POI — becomes the initial minimum.
    lines.append("    dx = qx_rel - p1x")
    lines.append("    dy = qy_rel - p1y")
    lines.append("    min_dist = dx * dx + dy * dy")
    lines.append("    min_id = p1_id + encrypted_zero")

    # Linear scan: compare remaining POIs one by one.
    for i in range(2, n + 1):
        lines.append(f"    dx = qx_rel - p{i}x")
        lines.append(f"    dy = qy_rel - p{i}y")
        lines.append(f"    d = dx * dx + dy * dy")
        lines.append(f"    is_new_min = d < min_dist")
        lines.append(f"    min_dist = np.where(is_new_min, d, min_dist)")
        lines.append(f"    min_id = np.where(is_new_min, p{i}_id + encrypted_zero, min_id)")

    lines.append("    return min_id, min_dist")

    code = "\n".join(lines)
    namespace = {"np": np}
    exec(code, namespace)  # noqa: S102
    return namespace["circuit"]


def _make_encryption_config(n: int) -> dict:
    config: dict = {"qx_rel": "encrypted", "qy_rel": "encrypted"}
    for i in range(1, n + 1):
        config[f"p{i}x"] = "clear"
        config[f"p{i}y"] = "clear"
        config[f"p{i}_id"] = "clear"
    return config


# ---------------------------------------------------------------------------
# Inputset generation  (optimised)
# ---------------------------------------------------------------------------

def _build_inputset(n: int) -> list:
    """
    Minimal inputset: exactly 3 samples for any N.

    Concrete traces the circuit to infer the value range of every intermediate
    signal and allocate the right number of bits.  Three samples are enough:

    Sample A — user at (0, 0), all POIs at (COORD_MAX_X, COORD_MAX_Y)
        • dist² = 11²+11² = 242  →  Concrete allocates 8-bit integers
        • min_id = 1  (no update: all distances equal, strict < never True)
        • qx_rel = 0, qy_rel = 0  (minimum user coordinates)
        • np.where condition always False  →  exercises the False branch

    Sample B — user at (COORD_MAX_X, COORD_MAX_Y), all POIs at (0, 0)
        • Same max dist² = 242
        • qx_rel = 11, qy_rel = 11  (maximum user coordinates)
        • min_id = 1

    Sample C — user at centre (cx, cy), last POI at (cx, cy), all others at (0, 0)
        • Last POI wins: dist²=0; all others dist²=cx²+cy²=60
        • min_id = N  →  combined with A&B giving min_id=1, Concrete infers
          min_id ∈ [1, N] and allocates ⌈log₂(N)⌉ bits correctly
        • dist² = 0  →  Concrete sees the minimum dist² value
        • np.where condition True for the last iteration  →  exercises the True branch

    Why not one sample per slot (the previous N+2 approach)?
    Concrete only needs the VALUE RANGE of each signal, not every individual
    value in that range.  Seeing min_id=1 (A&B) and min_id=N (C) is enough
    to infer [1..N].  The intermediate IDs 2..N-1 add no new bit-width
    information and only inflate tracing time.
    """
    cx = COORD_MAX_X // 2   # 5
    cy = COORD_MAX_Y // 2   # 5

    # ── Sample A: user at origin, all POIs at far corner ──
    args: list = [np.int64(0), np.int64(0)]
    for i in range(n):
        args += [np.int64(COORD_MAX_X), np.int64(COORD_MAX_Y), np.int64(i + 1)]
    sample_a = tuple(args)

    # ── Sample B: user at far corner, all POIs at origin ──
    args = [np.int64(COORD_MAX_X), np.int64(COORD_MAX_Y)]
    for i in range(n):
        args += [np.int64(0), np.int64(0), np.int64(i + 1)]
    sample_b = tuple(args)

    # ── Sample C: only the last POI wins ──
    # Shows min_id=N (max), dist²=0 (min), and exercises the True branch.
    args = [np.int64(cx), np.int64(cy)]
    for i in range(n):
        if i == n - 1:
            px, py = cx, cy   # last POI at user position → dist²=0, wins
        else:
            px, py = 0, 0     # all others at origin → dist²=113, lose
        args += [np.int64(px), np.int64(py), np.int64(i + 1)]
    sample_c = tuple(args)

    return [sample_a, sample_b, sample_c]


# ---------------------------------------------------------------------------
# Compile one N
# ---------------------------------------------------------------------------

def compile_for_n(n: int) -> None:
    server_path = ARTIFACTS_DIR / f"server_n{n}.zip"
    specs_path = ARTIFACTS_DIR / f"client_specs_n{n}.bin"

    fn = _make_circuit_fn(n)
    enc_cfg = _make_encryption_config(n)
    inputset = _build_inputset(n)

    # Circuit has (n-1) iterations × 3 PBS operations each.
    n_pbs = max(0, (n - 1) * 3)
    print(
        f"[N={n:3d}] Compiling — {len(inputset)} inputset samples, "
        f"~{n_pbs} PBS ops, p_error={_P_ERROR:.0e}",
        flush=True,
    )

    t0 = time.time()

    compiler = fhe.Compiler(fn, enc_cfg)
    circuit = compiler.compile(
        inputset,
        configuration=fhe.Configuration(
            p_error=_P_ERROR,
            compress_evaluation_keys=True,
        ),
    )

    circuit.server.save(server_path)
    specs_path.write_bytes(circuit.client.specs.serialize())

    elapsed = time.time() - t0
    mins, secs = divmod(int(elapsed), 60)
    print(
        f"[N={n:3d}] Done in {mins}m {secs:02d}s"
        f" — server: {server_path.name}  specs: {specs_path.name}",
        flush=True,
    )

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(
        f"Compiling Concrete find-minimum circuits for N = {SUPPORTED_N}\n"
        f"  Inputset: 3 samples per circuit (was ~4N+24)\n"
        f"  Error budget: p_error={_P_ERROR:.0e} per PBS (circuit-size independent)\n",
        flush=True,
    )
    t_total = time.time()
    for n in SUPPORTED_N:
        compile_for_n(n)
    elapsed = time.time() - t_total
    mins, secs = divmod(int(elapsed), 60)
    print(f"\nAll circuits compiled in {mins}m {secs:02d}s.", flush=True)

if __name__ == "__main__":
    main()
