from ..poi_search.engines.core_concrete import execute_concrete_evaluation
from ..poi_search.engines.openfhe_ss_engine import (
    execute_openfhe_ss_upload_keys,
    execute_openfhe_ss_evaluate,
)
from .repository import PoiRepository
from .schemas import (
    ConcreteEvaluationRequest,
    OpenFHESSEvaluateRequest,
    OpenFHESSUploadKeysRequest,
    ServiceProviderNearestKRequest,
)
from .scenarios.nearest_k import execute_nearest_k


class PoiSearchServiceProviderService:
    def __init__(self):
        self.repository = PoiRepository()

    def nearest_k_by_category(self, request: ServiceProviderNearestKRequest) -> dict:
        return execute_nearest_k(request)

    def list_categories(self) -> dict:
        return {"categories": self.repository.list_categories()}

    def concrete_evaluate(self, request: ConcreteEvaluationRequest) -> dict:
        return execute_concrete_evaluation(request)

    def openfhe_ss_upload_keys(self, request: OpenFHESSUploadKeysRequest) -> dict:
        return execute_openfhe_ss_upload_keys(
            crypto_context_b64=request.crypto_context_b64,
            public_key_b64=request.public_key_b64,
            eval_mult_keys_b64=request.eval_mult_keys_b64,
            eval_automorphism_keys_b64=request.eval_automorphism_keys_b64,
            n_candidates=request.n_candidates,
        )

    def openfhe_ss_evaluate(self, request: OpenFHESSEvaluateRequest) -> dict:
        return execute_openfhe_ss_evaluate(
            key_id=request.key_id,
            encrypted_qy=request.encrypted_qy,
            encrypted_qx=request.encrypted_qx,
            category=request.category,
            n_candidates=request.n_candidates,
        )

    def category_count(self, category: str) -> dict:
        count = self.repository.count_by_category(category)
        return {"category": category, "count": count}

