# client_app/tools/compile_distance_circuit.py

from pathlib import Path

import numpy as np
from concrete import fhe


CLIENT_APP_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

SERVER_PATH = ARTIFACTS_DIR / "server.zip"
CLIENT_SPECS_PATH = ARTIFACTS_DIR / "client_specs.bin"


def sorted_top2_by_distance(
    qx_rel: np.int64,
    qy_rel: np.int64,
    p1x_rel: np.int64,
    p1y_rel: np.int64,
    p1_id: np.int64,
    p2x_rel: np.int64,
    p2y_rel: np.int64,
    p2_id: np.int64,
) -> tuple[np.int64, np.int64, np.int64, np.int64]:
    """
    Concrete circuit for encrypted server-side sorting of 2 POIs.

    Encrypted:
      qx_rel, qy_rel = user coordinates after quantization and origin shifting

    Clear:
      p1x_rel, p1y_rel, p1_id = public POI 1 data
      p2x_rel, p2y_rel, p2_id = public POI 2 data

    Output:
      first_id, first_dist2, second_id, second_dist2

    The comparison d1 <= d2 is evaluated inside the encrypted circuit.
    """

    dx1 = qx_rel - p1x_rel
    dy1 = qy_rel - p1y_rel
    d1 = dx1 * dx1 + dy1 * dy1

    dx2 = qx_rel - p2x_rel
    dy2 = qy_rel - p2y_rel
    d2 = dx2 * dx2 + dy2 * dy2

    p1_is_first = d1 <= d2

    # Convert clear ids into encrypted values by adding encrypted zero.
    encrypted_zero = qx_rel - qx_rel
    p1_id_enc = p1_id + encrypted_zero
    p2_id_enc = p2_id + encrypted_zero

    first_id = np.where(p1_is_first, p1_id_enc, p2_id_enc)
    first_dist2 = np.where(p1_is_first, d1, d2)

    second_id = np.where(p1_is_first, p2_id_enc, p1_id_enc)
    second_dist2 = np.where(p1_is_first, d2, d1)

    return first_id, first_dist2, second_id, second_dist2


def build_inputset() -> list[tuple[np.int64, ...]]:
    """
    Small-range inputset.

    Important:
    This circuit uses server-side encrypted comparison, so the numeric range
    must be kept small. Runtime Concrete coordinates must also stay in this
    small range.
    """
    samples: list[tuple[np.int64, ...]] = []

    coord_values = [
        np.int64(0),
        np.int64(2),
        np.int64(4),
        np.int64(8),
        np.int64(12),
        np.int64(15),
    ]

    id1 = np.int64(1)
    id2 = np.int64(2)

    for qx in coord_values:
        for qy in coord_values:
            samples.append(
                (
                    qx,
                    qy,
                    np.int64(2),
                    np.int64(2),
                    id1,
                    np.int64(12),
                    np.int64(12),
                    id2,
                )
            )

            samples.append(
                (
                    qx,
                    qy,
                    np.int64(12),
                    np.int64(12),
                    id1,
                    np.int64(2),
                    np.int64(2),
                    id2,
                )
            )

    boundary_cases = [
        (0, 0, 0, 0, 1, 15, 15, 2),
        (15, 15, 0, 0, 1, 15, 15, 2),
        (8, 8, 4, 4, 1, 12, 12, 2),
        (8, 8, 12, 12, 1, 4, 4, 2),
        (2, 14, 2, 14, 1, 14, 2, 2),
        (14, 2, 2, 14, 1, 14, 2, 2),
        (6, 6, 4, 4, 1, 8, 8, 2),
        (6, 6, 8, 8, 1, 4, 4, 2),
    ]

    for case in boundary_cases:
        samples.append(tuple(np.int64(v) for v in case))

    return samples


def main() -> None:
    compiler = fhe.Compiler(
        sorted_top2_by_distance,
        {
            "qx_rel": "encrypted",
            "qy_rel": "encrypted",
            "p1x_rel": "clear",
            "p1y_rel": "clear",
            "p1_id": "clear",
            "p2x_rel": "clear",
            "p2y_rel": "clear",
            "p2_id": "clear",
        },
    )

    inputset = build_inputset()

    print(
        f"Compiling Concrete top-2 sorting circuit with {len(inputset)} samples...",
        flush=True,
    )

    circuit = compiler.compile(inputset)

    circuit.server.save(SERVER_PATH)
    CLIENT_SPECS_PATH.write_bytes(circuit.client.specs.serialize())

    print(f"Saved server artifact to: {SERVER_PATH}", flush=True)
    print(f"Saved client specs to: {CLIENT_SPECS_PATH}", flush=True)


if __name__ == "__main__":
    main()