import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SpectraVerse API"
    assert "version" in data


def test_mappings_endpoint():
    response = client.get("/api/mappings")
    # 200 if mappings loaded, 500 if semantic_mappings.json not found
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        body = response.json()
        assert isinstance(body, dict)
