from .ml_model import (
    is_ready,
    features_to_array,
    predict_plaintext,
    predict_fhe_simulate,
    predict_fhe_execute,
)
from .schemas import AnomalyPredictRequest, AnomalyPredictResponse, SchemeTiming


class AnomalyDetectionService:
    def ready(self) -> bool:
        return is_ready()

    async def predict(self, request: AnomalyPredictRequest) -> AnomalyPredictResponse:
        feat_dict = request.features.model_dump()
        X = features_to_array(feat_dict)

        pt_pred, pt_ms = predict_plaintext(X)
        sim_pred, sim_ms = predict_fhe_simulate(X)
        exec_result = predict_fhe_execute(X)

        return AnomalyPredictResponse(
            plaintext=SchemeTiming(prediction=pt_pred, inference_ms=pt_ms),
            fhe_simulate=SchemeTiming(prediction=sim_pred, inference_ms=sim_ms),
            fhe_execute=(
                SchemeTiming(prediction=exec_result[0], inference_ms=exec_result[1])
                if exec_result is not None
                else None
            ),
        )
