"""Integration test for POST /api/v1/webhook/manychat — uses TestClient."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_webhook_rejects_missing_signature(client):
    response = client.post("/api/v1/webhook/manychat", json={})
    assert response.status_code == 422  # missing header → validation error
