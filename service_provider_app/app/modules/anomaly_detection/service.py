import json
import time

import joblib

from ...core.concrete_ml_server_runtime import MODELS_DIR, ConcreteMLServerRuntime

DECISION_THRESHOLD = 0.25


class AnomalyDetectionServiceProviderService:
    def __init__(self) -> None:
        self.feature_cols: list[str] | None = None
        self.plaintext_model = None
        self.samples: list[dict] | None = None

        feature_cols_path = MODELS_DIR / "feature_cols.json"
        if feature_cols_path.exists():
            self.feature_cols = json.loads(feature_cols_path.read_text())

        plaintext_model_path = MODELS_DIR / "plaintext_model.joblib"
        if plaintext_model_path.exists():
            self.plaintext_model = joblib.load(plaintext_model_path)

        samples_path = MODELS_DIR / "test_samples.json"
        if samples_path.exists():
            self.samples = json.loads(samples_path.read_text())

        self.fhe_runtime = ConcreteMLServerRuntime()

    def _get_sample(self, sample_id: int) -> dict:
        if not self.samples:
            raise FileNotFoundError(
                f"Demo samples not found at {MODELS_DIR / 'test_samples.json'}. "
                "Rerun the training notebook to produce them."
            )

        for sample in self.samples:
            if sample["id"] == sample_id:
                return sample

        raise ValueError(f"No demo sample with id={sample_id}")

    def list_samples(self) -> dict:
        if not self.samples:
            raise FileNotFoundError(
                f"Demo samples not found at {MODELS_DIR / 'test_samples.json'}. "
                "Rerun the training notebook to produce them."
            )

        return {
            "samples": [
                {
                    "id": sample["id"],
                    "label": sample["label"],
                    "true_label": sample["true_label"],
                    "features": sample["features"],
                }
                for sample in self.samples
            ]
        }

    def predict_plaintext(self, sample_id: int) -> dict:
        if self.plaintext_model is None:
            raise FileNotFoundError(
                f"Plaintext model not found at {MODELS_DIR / 'plaintext_model.joblib'}. "
                "Rerun the training notebook to produce it."
            )

        sample = self._get_sample(sample_id)

        t0 = time.time()
        proba = float(self.plaintext_model.predict_proba([sample["features"]])[0][1])
        latency_ms = (time.time() - t0) * 1000

        return {
            "probability": proba,
            "prediction": int(proba >= DECISION_THRESHOLD),
            "true_label": sample["true_label"],
            "latency_ms": latency_ms,
        }

    def fhe_evaluate(self, encrypted_query_b64: str, evaluation_keys_b64: str) -> dict:
        return self.fhe_runtime.run(encrypted_query_b64, evaluation_keys_b64)
