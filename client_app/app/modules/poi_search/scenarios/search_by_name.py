# client_app/app/modules/poi_search/scenarios/search_by_name.py
from urllib.parse import quote

from ....infrastructure.http_client import get_from_service_provider


async def execute_search_by_name(query: str, limit: int = 10) -> dict:
    encoded_query = quote(query)
    return await get_from_service_provider(
        f"/service/poi/search-by-name?q={encoded_query}&limit={limit}"
    )