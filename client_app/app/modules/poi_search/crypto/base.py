from abc import ABC, abstractmethod


class ClientCryptoAdapter(ABC):

    #prepare the query before it is sent to the server
    @abstractmethod
    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        pass

    @abstractmethod
    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        pass