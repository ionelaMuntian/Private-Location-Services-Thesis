from abc import ABC, abstractmethod


class ServiceProviderEngine(ABC):
    @abstractmethod
    def compute_nearest_k(self, category: str, k: int, query: dict, candidates: list[dict]) -> dict:
        pass