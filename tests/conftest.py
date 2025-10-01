import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Resolve repo root no matter where pytest is run from
ROOT = Path(__file__).resolve().parents[3]  # .../services/spice/tests -> repo root
META = ROOT / "services/spice/kernels/involution.tm"

os.environ.setdefault("DISABLE_RATE_LIMIT", "1")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ["SPICE_META"] = str(META)

# Import after env is set
from services.spice.main import app  # noqa: E402

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c