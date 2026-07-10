import time

from ...core.concrete_ml_client_runtime import ConcreteMLClientRuntime
from ...infrastructure.grpc_client import (
    get_from_service_provider,
    post_to_service_provider,
)

DECISION_THRESHOLD = 0.25


class AnomalyDetectionClientService:
    def __init__(self) -> None:
        self._samples_cache: dict[int, dict] | None = None
        self._fhe_runtime: ConcreteMLClientRuntime | None = None

    async def _ensure_samples(self) -> dict[int, dict]:
        if self._samples_cache is None:
            result = await get_from_service_provider("/service/anomaly-detection/samples")
            self._samples_cache = {sample["id"]: sample for sample in result["samples"]}
        return self._samples_cache

    async def list_samples(self) -> dict:
        samples = await self._ensure_samples()
        return {
            "samples": [
                {"id": s["id"], "label": s["label"], "true_label": s["true_label"]}
                for s in samples.values()
            ]
        }

    def _get_fhe_runtime(self) -> ConcreteMLClientRuntime:
        if self._fhe_runtime is None:
            self._fhe_runtime = ConcreteMLClientRuntime()
        return self._fhe_runtime

    async def _run_plaintext(self, sample_id: int) -> dict:
        return await post_to_service_provider(
            "/service/anomaly-detection/predict-plaintext",
            {"sample_id": sample_id},
        )

    async def _run_encrypted(self, sample_id: int) -> dict:
        samples = await self._ensure_samples()
        if sample_id not in samples:
            raise ValueError(f"No demo sample with id={sample_id}")

        sample = samples[sample_id]
        runtime = self._get_fhe_runtime()

        t0 = time.time()
        encrypted_query_b64, evaluation_keys_b64 = runtime.encrypt_sample(sample["features"])

        response = await post_to_service_provider(
            "/service/anomaly-detection/fhe-evaluate",
            {
                "encrypted_query_b64": encrypted_query_b64,
                "evaluation_keys_b64": evaluation_keys_b64,
            },
        )

        proba = runtime.decrypt_result(response["encrypted_result_b64"])
        latency_ms = (time.time() - t0) * 1000

        return {
            "probability": proba,
            "prediction": int(proba >= DECISION_THRESHOLD),
            "true_label": sample["true_label"],
            "latency_ms": latency_ms,
        }

    async def infer(self, sample_id: int, mode: str) -> dict:
        result: dict = {"plaintext": None, "encrypted": None}

        if mode in ("plaintext", "both"):
            result["plaintext"] = await self._run_plaintext(sample_id)

        if mode in ("encrypted", "both"):
            result["encrypted"] = await self._run_encrypted(sample_id)

        return result
