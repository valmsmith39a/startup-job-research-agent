from fastapi.testclient import TestClient

from job_research_api.main import create_app


def test_health_is_ok_without_a_token() -> None:
    with TestClient(create_app(api_key="test-key-0123456789")) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_ok_with_auth_disabled() -> None:
    with TestClient(create_app(api_key=None)) as client:
        assert client.get("/health").json() == {"status": "ok"}
