from fastapi.testclient import TestClient

from app.main import app


def test_ui_routes_serve_agent_bank_shell():
    client = TestClient(app)

    for path in ("/qa", "/documents"):
        response = client.get(path)

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "MediaX Agent Bank" in response.text


def test_root_redirects_to_qa():
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/qa"


def test_ui_routes_are_hidden_from_openapi():
    paths = app.openapi()["paths"]

    assert "/" not in paths
    assert "/qa" not in paths
    assert "/documents" not in paths
