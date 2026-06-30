from .base import ClientCryptoAdapter

class PlaintextClientAdapter(ClientCryptoAdapter):
    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        return {
            "plaintext_query": {
                "latitude_m": latitude,
                "longitude_m": longitude,
            },
            "encrypted_query": None,
            "local_state": None,
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        return response_data["results"]