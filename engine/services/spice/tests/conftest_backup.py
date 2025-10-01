import os

import pytest
from fastapi.testclient import TestClient

# Make rate limiting non-blocking for most tests
os.environ["DISABLE_RATE_LIMIT"] = "1"
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

# IMPORTANT: kernels must be present on disk
os.environ.setdefault("SPICE_META", "services/spice/kernels/involution.tm")

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
