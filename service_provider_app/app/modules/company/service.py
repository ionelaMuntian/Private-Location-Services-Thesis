# service_provider_app/app/modules/company/service.py

from .openfhe_compliance_engine import OpenFHEComplianceEngine
from .schemas import ComplianceEvaluationRequest


class CompanyComplianceService:
    def __init__(self) -> None:
        self.engine = OpenFHEComplianceEngine()

    def evaluate_compliance(self, request: ComplianceEvaluationRequest) -> dict:
        return self.engine.evaluate(request.model_dump())