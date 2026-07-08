from abc import ABC, abstractmethod


class ClientCryptoAdapter(ABC):
    @abstractmethod
    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        pass

    def build_public_args_for_candidates(
        self,
        metadata: dict,
        candidates: list[dict],
        local_state: dict,
    ) -> list[dict]:
        raise NotImplementedError(
            "This adapter does not support candidate-side public arg building"
        )

    @abstractmethod
    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        pass