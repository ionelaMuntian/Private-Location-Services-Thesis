# client_app/tools/compile_distance_circuit.py
from pathlib import Path

import numpy as np
from concrete import fhe


CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

SERVER_PATH = ARTIFACTS_DIR / "server.zip"
CLIENT_SPECS_PATH = ARTIFACTS_DIR / "client_specs.bin"


def squared_distance(qx: np.int64, qy: np.int64, px: np.int64, py: np.int64) -> np.int64:
    dx = qx - px
    dy = qy - py
    return dx * dx + dy * dy


def build_inputset() -> list[tuple[np.int64, np.int64, np.int64, np.int64]]:
    # Wider ranges around current Cluj-area quantized coordinates
    query_x_vals = [np.int64(v) for v in range(23550, 23750, 10)]
    point_x_vals = [np.int64(v) for v in range(23550, 23750, 10)]
    query_y_vals = [np.int64(v) for v in range(57350, 57550, 10)]
    point_y_vals = [np.int64(v) for v in range(57350, 57550, 10)]

    inputset: list[tuple[np.int64, np.int64, np.int64, np.int64]] = []
    for qx in query_x_vals:
        for qy in query_y_vals:
            for px in point_x_vals:
                for py in point_y_vals:
                    inputset.append((qx, qy, px, py))

    return inputset


def main() -> None:
    compiler = fhe.Compiler(
        squared_distance,
        {
            "qx": "encrypted",
            "qy": "encrypted",
            "px": "clear",
            "py": "clear",
        },
    )

    inputset = build_inputset()
    circuit = compiler.compile(inputset)

    circuit.server.save(SERVER_PATH)
    CLIENT_SPECS_PATH.write_bytes(circuit.client.specs.serialize())

    print(f"Saved server artifact to: {SERVER_PATH}")
    print(f"Saved client specs to: {CLIENT_SPECS_PATH}")


if __name__ == "__main__":
    main()