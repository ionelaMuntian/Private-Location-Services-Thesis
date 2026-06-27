# service_provider_app/app/grpc_server.py
import asyncio
import base64
import json
import traceback
from urllib.parse import parse_qs, urlparse

import grpc
from pydantic import ValidationError

from .generated import service_provider_pb2, service_provider_pb2_grpc
from .modules.company.schemas import ComplianceEvaluationRequest
from .modules.company.service import CompanyComplianceService
from .modules.poi_search.engines.core_concrete import execute_concrete_upload_keys
from .modules.poi_search.engines.openfhe_ss_engine import (
    execute_openfhe_ss_upload_keys,
)
from .modules.poi_search.schemas import (
    ConcreteCandidatesRequest,
    ConcreteEvaluationRequest,
    OpenFHESSEvaluateRequest,
    OpenFHESSUploadKeysRequest,
    ServiceProviderNearestKRequest,
)
from .modules.poi_search.service import PoiSearchServiceProviderService

poi_service = PoiSearchServiceProviderService()
company_service = CompanyComplianceService()

GRPC_MAX_MESSAGE_SIZE = -1  # unlimited; senders are responsible for keeping payloads sane


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


def _openfhe_ss_key_upload_response(
    status_code: int,
    payload: dict,
) -> service_provider_pb2.OpenFHESSKeyUploadResponse:
    return service_provider_pb2.OpenFHESSKeyUploadResponse(
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
                result = poi_service.nearest_k_by_category(dto)
                return _json_response(200, result)

            if method == "GET" and clean_path == "/service/poi/categories":
                result = poi_service.list_categories()
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/poi/concrete/candidates":
                dto = ConcreteCandidatesRequest(**payload)
                result = poi_service.concrete_candidates(dto)
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/poi/concrete/evaluate":
                dto = ConcreteEvaluationRequest(**payload)
                result = poi_service.concrete_evaluate(dto)
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/poi/openfhe-ss/upload-keys":
                dto = OpenFHESSUploadKeysRequest(**payload)
                result = poi_service.openfhe_ss_upload_keys(dto)
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/poi/openfhe-ss/evaluate":
                dto = OpenFHESSEvaluateRequest(**payload)
                result = poi_service.openfhe_ss_evaluate(dto)
                return _json_response(200, result)

            if method == "GET" and clean_path == "/service/poi/category-count":
                category_values = query_params.get("category", [])
                if not category_values:
                    return _json_response(422, {"detail": "Missing required query parameter: category"})
                result = poi_service.category_count(category=category_values[0])
                return _json_response(200, result)

            if method == "POST" and clean_path == "/service/company/compliance/evaluate":
                dto = ComplianceEvaluationRequest(**payload)
                result = company_service.evaluate_compliance(dto)
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
            print(f"[gRPC handler error] {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            return _json_response(
                500,
                {
                    "detail": f"{type(exc).__name__}: {exc}",
                },
            )

    async def UploadConcreteKeys(self, request_iterator, context):
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

    async def UploadOpenFHESSKeys(self, request_iterator, context):
        try:
            buffers: dict = {}
            n_candidates = 128

            async for chunk in request_iterator:
                key_name = chunk.key_name
                if key_name == "n_candidates":
                    n_candidates = int(chunk.data.decode())
                else:
                    if key_name not in buffers:
                        buffers[key_name] = bytearray()
                    buffers[key_name].extend(chunk.data)

            def to_b64(name: str) -> str:
                return base64.b64encode(bytes(buffers.get(name, b""))).decode()

            result = execute_openfhe_ss_upload_keys(
                crypto_context_b64=to_b64("crypto_context"),
                public_key_b64=to_b64("public_key"),
                eval_mult_keys_b64=to_b64("eval_mult_keys"),
                n_candidates=n_candidates,
            )
            return _openfhe_ss_key_upload_response(200, result)

        except Exception as exc:
            print(
                f"[gRPC UploadOpenFHESSKeys error] {type(exc).__name__}: {exc}",
                flush=True,
            )
            traceback.print_exc()
            return _openfhe_ss_key_upload_response(
                500,
                {"detail": f"{type(exc).__name__}: {exc}"},
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