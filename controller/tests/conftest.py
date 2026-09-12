import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.main import create_app
from app.store import MemoryStore


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        store_backend="memory",
        enrollment_key="test-enrollment-key",
        admin_token="test-admin-token",
        offline_after_sec=120,
        gcp_project="firewall-ai",
    )


@pytest.fixture
def client(settings: Settings, store: MemoryStore) -> TestClient:
    app = create_app(settings=settings, store=store)
    return TestClient(app)
