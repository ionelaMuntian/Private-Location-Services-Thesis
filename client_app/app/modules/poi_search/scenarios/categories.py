from ....infrastructure.grpc_client import get_from_service_provider


async def execute_list_categories() -> dict:
    return await get_from_service_provider("/service/poi/categories")