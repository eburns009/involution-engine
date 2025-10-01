import httpx
import logging
from typing import Dict, Any, List
from ..config import GeocodeConfig
from ..errors import map_http_client_error, bad_request

logger = logging.getLogger(__name__)


async def geocode_search(
    query: str,
    limit: int,
    config: GeocodeConfig
) -> List[Dict[str, Any]]:
    """
    Search for geographic locations using geocoding service.

    Args:
        query: Search query
        limit: Maximum number of results
        config: Geocoding service configuration

    Returns:
        List of location results

    Raises:
        HTTPException: Mapped from geocoding errors
    """
    if not query.strip():
        bad_request(
            "INPUT.INVALID",
            "Empty search query",
            "Search query cannot be empty.",
            "Provide a location name to search for."
        )

    try:
        timeout = httpx.Timeout(config.timeout_ms / 1000.0)
        params = {
            "q": query.strip(),
            "limit": min(limit, 20),  # Cap at 20 results
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{config.base_url}/search",
                params=params
            )
            response.raise_for_status()

            raw_results = response.json()

            # Transform Nominatim results to our format
            results = []
            for item in raw_results[:limit]:
                result = {
                    "name": item.get("display_name", ""),
                    "lat": float(item.get("lat", 0)),
                    "lon": float(item.get("lon", 0))
                }

                # Extract country and admin1 if available
                address = item.get("address", {})
                if address:
                    result["country"] = address.get("country", "")
                    result["admin1"] = (
                        address.get("state") or
                        address.get("province") or
                        address.get("region") or
                        ""
                    )

                results.append(result)

            if not results:
                bad_request(
                    "GEOCODE.NOT_FOUND",
                    "Location not found",
                    "No results found for search query.",
                    "Try a more specific or different location name."
                )

            return results

    except httpx.HTTPStatusError as e:
        logger.error(f"Geocoding HTTP error: {e.response.status_code} - {e.response.text}")
        map_http_client_error(e, "geocoding")

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error(f"Geocoding connection error: {e}")
        map_http_client_error(e, "geocoding")

    except Exception as e:
        logger.error(f"Unexpected geocoding error: {e}")
        map_http_client_error(e, "geocoding")