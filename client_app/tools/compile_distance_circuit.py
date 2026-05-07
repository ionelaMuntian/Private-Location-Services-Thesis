from pathlib import Path

import numpy as np
from concrete import fhe


CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

SERVER_PATH = ARTIFACTS_DIR / "server.zip"
CLIENT_SPECS_PATH = ARTIFACTS_DIR / "client_specs.bin"

# Local origin for Cluj / your dataset area, after quantization
# original meters are around lon_m=2362254, lat_m=5741384
# with scale_divisor=100, absolute quantized values are around 23622 and 57414
ORIGIN_X_Q = np.int64(23600)
ORIGIN_Y_Q = np.int64(57400)

def squared_distance(
    qx_rel: np.int64,
    qy_rel: np.int64,
    px_rel: np.int64,
    py_rel: np.int64,
) -> np.int64:
    dx = qx_rel - px_rel
    dy = qy_rel - py_rel
    return dx * dx + dy * dy


def build_inputset() -> list[tuple[np.int64, np.int64, np.int64, np.int64]]:
    # Relative quantized coordinates.
    # Example:
    # lon_m = 2362254 -> 23622 -> relative to 23600 = 22
    # lat_m = 5741384 -> 57414 -> relative to 57400 = 14

    x_vals = [np.int64(v) for v in range(0, 80, 5)]
    y_vals = [np.int64(v) for v in range(0, 80, 5)]

    inputset: list[tuple[np.int64, np.int64, np.int64, np.int64]] = []

    for qx in x_vals:
        for qy in y_vals:
            for px in x_vals:
                for py in y_vals:
                    inputset.append((qx, qy, px, py))

    return inputset


def main() -> None:
    compiler = fhe.Compiler(
        squared_distance,
        {
            "qx_rel": "encrypted",
            "qy_rel": "encrypted",
            "px_rel": "clear",
            "py_rel": "clear",
        },
    )

    inputset = build_inputset()
    print(f"Compiling Concrete circuit with {len(inputset)} samples...")

    circuit = compiler.compile(inputset)

    circuit.server.save(SERVER_PATH)
    CLIENT_SPECS_PATH.write_bytes(circuit.client.specs.serialize())

    print(f"Saved server artifact to: {SERVER_PATH}")
    print(f"Saved client specs to: {CLIENT_SPECS_PATH}")


if __name__ == "__main__":
    main()