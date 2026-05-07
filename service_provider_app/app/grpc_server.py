# service_provider_app/app/grpc_server.py

import asyncio
import json
from urllib.parse import parse_qs, urlparse

import grpc
from pydantic import ValidationError

from .generated import service_provider_pb2, service_provider_pb2_grpc
from .modules.poi_search.engines.core_concrete import execute_concrete_upload_keys
from .modules.poi_search.schemas import (
    ConcreteCandidatesRequest,
    ConcreteEvaluationRequest,
    ServiceProviderNearestKRequest,
)
from .modules.poi_search.service import PoiSearchServiceProviderService


service = PoiSearchServiceProviderService()

# Must stay below 2,147,483,647 bytes because gRPC options use signed int.
# 1500 MB is enough for large encrypted responses without overflow.
GRPC_MAX_MESSAGE_SIZE = 1500 * 1024 * 1024


def _json_response(
    status_code: int,
    payload: dict,
) -> service_provider_pb2.ServiceProviderResponse:
    return service_provider_pb2.ServiceProviderResponse(
        status_code=status_code,
        json_payload=json.dumps(payload, ensure_ascii=False),
    )


def _key_upload_response(
    status_code: int,
    payload: dict,
) -> service_provider_pb2.ConcreteKeyUploadResponse:
    return service_provider_pb2.ConcreteKeyUploadResponse(
        status_code=status_code,
        json_payload=json.dumps(payload, ensure_ascii=False),
    )


class ServiceProviderGatewayServicer(
    service_provider_pb2_grpc.ServiceProviderGatewayServicer
):
    async def Call(self, request, context):
        try:
            method = request.method.upper()
            path = request.path
            payload = json.loads(request.json_payload or "{}")

            parsed = urlparse(path)
            clean_path = parsed.path
            query_params = parse_qs(parsed.query)

            if method == "POST" and clean_path == "/service/poi/nearest-k":
                dto = ServiceProviderNearestKRequest(**payload)
                result = service.nearest_k_by_category(dto)
                return _json_response(200, result)

            if method == "GET" and clean_path == "/service/poi/categories":
                result = service.list_categories()
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/poi/concrete/candidates":
                dto = ConcreteCandidatesRequest(**payload)
                result = service.concrete_candidates(dto)
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/poi/concrete/evaluate":
                dto = ConcreteEvaluationRequest(**payload)
                result = service.concrete_evaluate(dto)
                return _json_response(200, result)

            if method == "GET" and clean_path == "/service/poi/search-by-name":
                q_values = query_params.get("q", [])
                limit_values = query_params.get("limit", ["10"])

                if not q_values:
                    return _json_response(
                        422,
                        {"detail": "Missing required query parameter: q"},
                    )

                q = q_values[0]
                limit = int(limit_values[0])

                result = service.search_by_name(query=q, limit=limit)
                return _json_response(200, result)

            return _json_response(
                404,
                {
                    "detail": f"No gRPC route mapped for {method} {path}",
                },
            )

        except ValidationError as exc:
            return _json_response(
                422,
                {
                    "detail": exc.errors(),
                },
            )

        except Exception as exc:
            return _json_response(
                500,
                {
                    "detail": f"{type(exc).__name__}: {exc}",
                },
            )

    async def UploadConcreteKeys(self, request_iterator, context):
        """
        Streaming gRPC endpoint for Concrete evaluation keys.

        Concrete evaluation keys are very large. Sending them as base64 inside
        the normal JSON request caused the client container to be killed because
        the request became hundreds of MB.

        This endpoint receives the keys in chunks, stores them in memory through
        execute_concrete_upload_keys(), and returns a key_id. The later
        /service/poi/concrete/evaluate request sends only the key_id.
        """
        try:
            buffer = bytearray()
            total_chunks = 0

            async for chunk in request_iterator:
                buffer.extend(chunk.data)
                total_chunks += 1

            result = execute_concrete_upload_keys(bytes(buffer))
            result["received_chunks"] = total_chunks
            result["received_size_bytes"] = len(buffer)

            return _key_upload_response(200, result)

        except Exception as exc:
            return _key_upload_response(
                500,
                {
                    "detail": f"{type(exc).__name__}: {exc}",
                },
            )


async def serve() -> None:
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", GRPC_MAX_MESSAGE_SIZE),
            ("grpc.max_receive_message_length", GRPC_MAX_MESSAGE_SIZE),
        ],
        compression=grpc.Compression.Gzip,
    )

    service_provider_pb2_grpc.add_ServiceProviderGatewayServicer_to_server(
        ServiceProviderGatewayServicer(),
        server,
    )

    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)

    print(f"Service Provider gRPC server listening on {listen_addr}", flush=True)

    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())