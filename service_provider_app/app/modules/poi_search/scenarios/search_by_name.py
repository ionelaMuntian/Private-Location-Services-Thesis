from ..repository import PoiRepository

repository = PoiRepository()


def execute_search_by_name(query: str, limit: int = 10) -> dict:
    results = repository.search_by_name(query=query, limit=limit)

    return {
        "query": query,
        "count": len(results),
        "results": results,
    }