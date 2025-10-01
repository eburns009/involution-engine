import httpx
import logging
from typing import Dict, Any
from ..config import TimeConfig
from ..errors import handle_time_resolution_error

logger = logging.getLogger(__name__)


async def resolve_time(
    local_datetime: str,
    place: Dict[str, Any],
    config: TimeConfig,
    parity_profile: str = None
) -> str:
    """
    Resolve local datetime to UTC using time resolver service.

    Args:
        local_datetime: Local datetime string
        place: Place information with lat/lon
        config: Time resolver configuration
        parity_profile: Parity profile override

    Returns:
        UTC datetime string

    Raises:
        HTTPException: Mapped from time resolution errors
    """
    request_data = {
        "local_datetime": local_datetime,
        "place": place,
        "parity_profile": parity_profile or config.parity_profile_default
    }

    try:
        timeout = httpx.Timeout(config.timeout_ms / 1000.0 if hasattr(config, 'timeout_ms') else 5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{config.base_url}/v1/time/resolve",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            return result["utc"]

    except httpx.HTTPStatusError as e:
        logger.error(f"Time resolution HTTP error: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 400:
            try:
                error_detail = e.response.json()
                handle_time_resolution_error(Exception(error_detail.get("detail", str(e))))
            except:
                handle_time_resolution_error(e)
        else:
            handle_time_resolution_error(e)

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error(f"Time resolution connection error: {e}")
        handle_time_resolution_error(e)

    except Exception as e:
        logger.error(f"Unexpected time resolution error: {e}")
        handle_time_resolution_error(e)