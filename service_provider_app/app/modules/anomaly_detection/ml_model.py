"""
Loads trained anomaly-detection models from the models/ directory and exposes
predict helpers for plaintext, FHE-simulate, and FHE-execute inference.

Models are loaded once at module import time (startup).  If artifacts are
missing the module still imports cleanly; routes return 503 in that case.
"""
import json
import time
import logging
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent / "models"
_FEATURE_COLS_FILE = _MODELS_DIR / "feature_cols.json"
_PT_MODEL_FILE = _MODELS_DIR / "plaintext_model.joblib"
_SCALER_FILE = _MODELS_DIR / "scaler.joblib"
_FHE_MODEL_DIR = _MODELS_DIR / "fhe_model"

_pt_model = None
_scaler = None
_fhe_model = None
_fhe_model_sklearn = None   # concrete-ml model for simulate mode
_feature_cols: list[str] = []

def _load_models() -> None:
    global _pt_model, _scaler, _fhe_model, _fhe_model_sklearn, _feature_cols

    if not _FEATURE_COLS_FILE.exists():
        logger.warning("Anomaly detection: feature_cols.json not found — run training notebook first.")
        return

    _feature_cols = json.loads(_FEATURE_COLS_FILE.read_text())

    if _PT_MODEL_FILE.exists() and _SCALER_FILE.exists():
        _pt_model = joblib.load(_PT_MODEL_FILE)
        _scaler = joblib.load(_SCALER_FILE)
        logger.info("Anomaly detection: plaintext model loaded.")
    else:
        logger.warning("Anomaly detection: plaintext model or scaler not found.")

    if _FHE_MODEL_DIR.exists():
        try:
            from concrete.ml.deployment import FHEModelServer
            _fhe_model = FHEModelServer(str(_FHE_MODEL_DIR))
            _fhe_model.load()
            logger.info("Anomaly detection: FHE model server loaded.")
        except Exception as exc:
            logger.warning(f"Anomaly detection: could not load FHE model — {exc}")

        # Also load the sklearn-compatible concrete-ml model for simulate mode
        _fhe_sklearn_file = _FHE_MODEL_DIR / "sklearn_model.joblib"
        if _fhe_sklearn_file.exists():
            try:
                _fhe_model_sklearn = joblib.load(_fhe_sklearn_file)
                logger.info("Anomaly detection: FHE simulate model loaded.")
            except Exception as exc:
                logger.warning(f"Anomaly detection: could not load FHE simulate model — {exc}")


_load_models()


def is_ready() -> bool:
    return _pt_model is not None and _scaler is not None


def features_to_array(feature_dict: dict) -> np.ndarray:
    row = [float(feature_dict[col]) for col in _feature_cols]
    return np.array([row], dtype=np.float32)


def predict_plaintext(X_raw: np.ndarray) -> tuple[int, float]:
    X_s = _scaler.transform(X_raw)
    t0 = time.perf_counter()
    pred = int(_pt_model.predict(X_s)[0])
    ms = (time.perf_counter() - t0) * 1000
    return pred, round(ms, 3)


def predict_fhe_simulate(X_raw: np.ndarray) -> tuple[int, float]:
    X_s = _scaler.transform(X_raw)
    t0 = time.perf_counter()
    if _fhe_model_sklearn is not None:
        pred = int(_fhe_model_sklearn.predict(X_s, fhe="simulate")[0])
    else:
        # Fall back to plaintext if FHE model not available
        pred = int(_pt_model.predict(X_s)[0])
    ms = (time.perf_counter() - t0) * 1000
    return pred, round(ms, 3)


def predict_fhe_execute(X_raw: np.ndarray) -> tuple[int, float] | None:
    """True FHE evaluation via FHEModelServer.  Returns None if not available."""
    if _fhe_model is None:
        return None
    try:
        from concrete.ml.deployment import FHEModelClient
        client = FHEModelClient(str(_FHE_MODEL_DIR))
        client.generate_private_and_evaluation_keys()
        X_s = _scaler.transform(X_raw)
        serialized_enc = client.quantize_encrypt_serialize(X_s)
        eval_keys = client.get_serialized_evaluation_keys()
        t0 = time.perf_counter()
        encrypted_result = _fhe_model.run(serialized_enc, eval_keys)
        ms = (time.perf_counter() - t0) * 1000
        result = client.deserialize_decrypt_dequantize(encrypted_result)
        pred = int(result[0])
        return pred, round(ms, 3)
    except Exception as exc:
        logger.error(f"FHE execute failed: {exc}")
        return None
