
import time
from pathlib import Path

import numpy as np
from concrete import fhe

CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_N = [1, 5, 12, 13, 14, 15]

COORD_MAX_X = 11
COORD_MAX_Y = 11

_P_ERROR = 1e-6

def _make_circuit_fn(n: int):
    param_names = ["qx_rel", "qy_rel"]
    for i in range(1, n + 1):
        param_names += [f"p{i}x", f"p{i}y", f"p{i}_id"]

    lines = [f"def circuit({', '.join(param_names)}):"]
    lines.append("    encrypted_zero = qx_rel - qx_rel")

    lines.append("    dx = qx_rel - p1x")
    lines.append("    dy = qy_rel - p1y")
    lines.append("    min_dist = dx * dx + dy * dy")
    lines.append("    min_id = p1_id + encrypted_zero")

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
    exec(code, namespace)
    return namespace["circuit"]


def _make_encryption_config(n: int) -> dict:
    config: dict = {"qx_rel": "encrypted", "qy_rel": "encrypted"}
    for i in range(1, n + 1):
        config[f"p{i}x"] = "clear"
        config[f"p{i}y"] = "clear"
        config[f"p{i}_id"] = "clear"
    return config


def _build_inputset(n: int) -> list:
    cx = COORD_MAX_X // 2
    cy = COORD_MAX_Y // 2

    args: list = [np.int64(0), np.int64(0)]
    for i in range(n):
        args += [np.int64(COORD_MAX_X), np.int64(COORD_MAX_Y), np.int64(i + 1)]
    sample_a = tuple(args)

    args = [np.int64(COORD_MAX_X), np.int64(COORD_MAX_Y)]
    for i in range(n):
        args += [np.int64(0), np.int64(0), np.int64(i + 1)]
    sample_b = tuple(args)

    args = [np.int64(cx), np.int64(cy)]
    for i in range(n):
        if i == n - 1:
            px, py = cx, cy
        else:
            px, py = 0, 0
        args += [np.int64(px), np.int64(py), np.int64(i + 1)]
    sample_c = tuple(args)

    return [sample_a, sample_b, sample_c]


def compile_for_n(n: int) -> None:
    server_path = ARTIFACTS_DIR / f"server_n{n}.zip"
    specs_path = ARTIFACTS_DIR / f"client_specs_n{n}.bin"

    fn = _make_circuit_fn(n)
    enc_cfg = _make_encryption_config(n)
    inputset = _build_inputset(n)

    n_pbs = max(0, (n - 1) * 3)
    print(
        f"[N={n:3d}] Compiling - {len(inputset)} inputset samples, "
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
        f" - server: {server_path.name}  specs: {specs_path.name}",
        flush=True,
    )

def main() -> None:
    print(
        f"Compiling Concrete find-minimum circuits for N = {SUPPORTED_N}\n"
        f"  Inputset: 3 samples per circuit (was 4N+24)\n"
        f"  Error budget: p_error={_P_ERROR:.0e} per PBS (circuit-size independent)\n",
        flush=True,
    )
    t_total = time.time()
    for n in SUPPORTED_N:
        compile_for_n(n)
    elapsed = time.time() - t_total
    mins, secs = divmod(int(elapsed), 60)
    print(f"\nAll circuits compiled in {mins}m {secs:02d}s", flush=True)

if __name__ == "__main__":
    main()
