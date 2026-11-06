import pytest
from fastapi.testclient import TestClient

from token_vault.app import create_app
from token_vault.config import Settings
from token_vault.llm.mock_provider import MockProvider

HOST_PIN = "test-pin"


@pytest.fixture()
def client() -> TestClient:
    settings = Settings(host_pin=HOST_PIN)
    settings.game.rate_limit_per_minute = 1000
    app = create_app(settings=settings, provider=MockProvider(), db_path=":memory:")
    return TestClient(app)


@pytest.fixture()
def player(client: TestClient) -> dict:
    me = client.post("/api/join", json={"name": "Tester", "team": "QA"}).json()
    client.headers["X-Player-Token"] = me["token"]
    return me


def host(client: TestClient, method: str, path: str, json: dict | None = None):
    return client.request(method, path, json=json, headers={"X-Host-Pin": HOST_PIN})
