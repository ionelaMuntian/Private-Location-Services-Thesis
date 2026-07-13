
from pathlib import Path

import numpy as np
from concrete import fhe

# paths to the output folders
CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# a circuit will be built for each N, where N is the no. of POIs in a category
SUPPORTED_N = [1, 5, 12, 13, 14, 15]

# all POIs are expected to be [0,11] range, and the library will know to set the correct parameters based on this constraint
COORD_MAX_X = 11
COORD_MAX_Y = 11

# The probability that a PBS produces a wrong result
_P_ERROR = 1e-6

# It dynamically generates the function which will become the FHE circuit
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

    # join all the lines in a single string
    code = "\n".join(lines)
    namespace = {"np": np}
    exec(code, namespace)
    return namespace["circuit"]

# makes a dictory which tells which coordinates are encrypted and which are plaintext
def _make_encryption_config(n: int) -> dict:
    config: dict = {"qx_rel": "encrypted", "qy_rel": "encrypted"}
    for i in range(1, n + 1):
        config[f"p{i}x"] = "clear"
        config[f"p{i}y"] = "clear"
        config[f"p{i}_id"] = "clear"
    return config

# it builds a representative input set for the circuit, s.t. the library will know to select the correct parameters
def _build_inputset(n: int) -> list:

    # the center of the range
    cx = COORD_MAX_X // 2
    cy = COORD_MAX_Y // 2

    # scenario 1: the client is at position (0,0), all the POIs are at max (11,11)
    args: list = [np.int64(0), np.int64(0)]
    for i in range(n):
        args += [np.int64(COORD_MAX_X), np.int64(COORD_MAX_Y), np.int64(i + 1)]
    sample_a = tuple(args)

    # scenario 2: the client is at position max (11,11), all the POIs are at (0,0)
    args = [np.int64(COORD_MAX_X), np.int64(COORD_MAX_Y)]
    for i in range(n):
        args += [np.int64(0), np.int64(0), np.int64(i + 1)]
    sample_b = tuple(args)

    # scenario 3: the client is at center (5,5), all the POIs are at (0,0), except the last which is at (5,5)
    args = [np.int64(cx), np.int64(cy)]
    for i in range(n):
        if i == n - 1:
            px, py = cx, cy
        else:
            px, py = 0, 0
        args += [np.int64(px), np.int64(py), np.int64(i + 1)]
    sample_c = tuple(args)

    return [sample_a, sample_b, sample_c]

# it generates and compiles one circuit
def compile_for_n(n: int) -> None:

    # it contains the compiled homomorphic circuit for the server and the spec for the client
    server_path = ARTIFACTS_DIR / f"server_n{n}.zip"
    specs_path = ARTIFACTS_DIR / f"client_specs_n{n}.bin"

    fn = _make_circuit_fn(n)
    enc_cfg = _make_encryption_config(n)
    inputset = _build_inputset(n)

    # compile the function
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

def main() -> None:
    for n in SUPPORTED_N:
        compile_for_n(n)

if __name__ == "__main__":
    main()
