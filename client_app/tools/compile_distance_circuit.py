# client_app/tools/compile_distance_circuit.py
#
# Compiles one Concrete FHE circuit per supported N value.
# Each circuit takes encrypted user coordinates + N clear POI inputs
# and returns the ID and squared distance of the closest POI (k=1).
#
# Supported N values: 1, 2, 5, 10, 20
# Artifacts saved to: client_app/.artifacts/concrete/
#   server_nN.zip        — loaded by the service provider
#   client_specs_nN.bin  — loaded by the client for key generation / encrypt / decrypt

from pathlib import Path

import numpy as np
from concrete import fhe

CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_N = [1, 2, 5, 10, 20]

# Cluj-Napoca dataset: after ÷1000 and origin shift the relative coordinates
# fit in [0, 7] × [0, 5].  Keeping values small is critical — larger ranges
# produce exponentially bigger evaluation keys and slower PBS operations.
COORD_VALUES = [0, 1, 2, 3, 4, 5, 6, 7]

# Pool of POI (px, py) positions used when building the inputset.
# Must cover the full coordinate range so Concrete compiles for every case.
_POI_COORD_POOL = [
    (0, 0), (7, 5), (1, 1), (6, 4), (3, 2),
    (4, 3), (2, 4), (5, 1), (0, 5), (7, 0),
    (2, 2), (5, 3), (1, 4), (6, 2), (3, 5),
    (4, 1), (0, 3), (7, 2), (2, 0), (5, 5),
]


# ---------------------------------------------------------------------------
# Circuit generation
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
# Inputset generation
# ---------------------------------------------------------------------------

def _build_inputset(n: int) -> list:
    """
    Generates a representative inputset for the N-POI circuit.

    Rules:
    - User coordinates vary over COORD_VALUES × COORD_VALUES (subset).
    - POI coordinates are drawn from _POI_COORD_POOL.
    - Extra samples ensure the minimum is at each position 0..N-1 so
      Concrete sees every branch of the np.where chain.
    """
    samples: list = []

    user_positions = [(qx, qy) for qx in [0, 1, 3, 5, 7] for qy in [0, 2, 5]]

    # General samples: POI coords from pool, varied user positions.
    for qx, qy in user_positions:
        args: list = [np.int64(qx), np.int64(qy)]
        for i in range(n):
            px, py = _POI_COORD_POOL[i % len(_POI_COORD_POOL)]
            args += [np.int64(px), np.int64(py), np.int64(i + 1)]
        samples.append(tuple(args))

    # Samples where each POI is the minimum — ensures all np.where branches
    # are exercised.
    for min_pos in range(n):
        for qx, qy in [(3, 3), (0, 0), (7, 5), (1, 4)]:
            args = [np.int64(qx), np.int64(qy)]
            for i in range(n):
                if i == min_pos:
                    # Place this POI at the user position (distance = 0).
                    px, py = qx, qy
                else:
                    # Place other POIs at the far corner.
                    px = 7 - qx if qx <= 3 else 0
                    py = 5 - qy if qy <= 2 else 0
                args += [np.int64(px), np.int64(py), np.int64(i + 1)]
            samples.append(tuple(args))

    # Boundary / edge cases.
    for qx, qy in [(0, 0), (7, 5), (3, 3)]:
        for offset in range(min(n, 4)):
            args = [np.int64(qx), np.int64(qy)]
            for i in range(n):
                px = (i + offset) % 8
                py = (i + offset) % 6
                args += [np.int64(px), np.int64(py), np.int64(i + 1)]
            samples.append(tuple(args))

    return samples


# ---------------------------------------------------------------------------
# Compile one N
# ---------------------------------------------------------------------------

def compile_for_n(n: int) -> None:
    server_path = ARTIFACTS_DIR / f"server_n{n}.zip"
    specs_path = ARTIFACTS_DIR / f"client_specs_n{n}.bin"

    fn = _make_circuit_fn(n)
    config = _make_encryption_config(n)
    inputset = _build_inputset(n)

    print(
        f"[N={n}] Compiling circuit with {len(inputset)} inputset samples...",
        flush=True,
    )

    compiler = fhe.Compiler(fn, config)
    circuit = compiler.compile(inputset)

    circuit.server.save(server_path)
    specs_path.write_bytes(circuit.client.specs.serialize())

    print(f"[N={n}] Saved server artifact : {server_path}", flush=True)
    print(f"[N={n}] Saved client specs    : {specs_path}", flush=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Compiling Concrete find-minimum circuits for N = {SUPPORTED_N}", flush=True)
    for n in SUPPORTED_N:
        compile_for_n(n)
    print("All circuits compiled successfully.", flush=True)


if __name__ == "__main__":
    main()
