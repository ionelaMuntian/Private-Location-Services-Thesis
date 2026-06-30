from fastapi import HTTPException

from .base import ServiceProviderEngine


class ConcreteEngine(ServiceProviderEngine):
    def compute_nearest_k(self, category: str, k: int, query: dict, candidates: list[dict]) -> dict:
        raise HTTPException(
            status_code=501,
            detail="Concrete uses the dedicated /concrete/candidates and /concrete/evaluate flow.",
        )