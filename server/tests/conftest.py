import pytest
import asyncio
import os


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the API service."""
    return os.getenv("ENGINE_BASE", "http://localhost:8080")


@pytest.fixture
def fort_knox_1962_utc():
    """Fort Knox 1962 canonical test time in UTC."""
    return "1962-07-03T04:33:00Z"


@pytest.fixture
def fort_knox_1962_local():
    """Fort Knox 1962 canonical test data for local time conversion."""
    return {
        "local_datetime": "1962-07-02T23:33:00",
        "place": {
            "name": "Fort Knox, Kentucky",
            "lat": 37.840347,
            "lon": -85.949127
        }
    }


@pytest.fixture
def basic_tropical_request(fort_knox_1962_utc):
    """Basic tropical zodiac position request."""
    return {
        "when": {"utc": fort_knox_1962_utc},
        "system": "tropical",
        "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
    }


@pytest.fixture
def basic_sidereal_request(fort_knox_1962_utc):
    """Basic sidereal zodiac position request."""
    return {
        "when": {"utc": fort_knox_1962_utc},
        "system": "sidereal",
        "ayanamsha": {"id": "FAGAN_BRADLEY_DYNAMIC"},
        "bodies": ["Sun", "Moon"]
    }