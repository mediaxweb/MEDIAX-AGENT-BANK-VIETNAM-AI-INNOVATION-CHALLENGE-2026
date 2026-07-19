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


def test_ui_offers_ten_demo_accounts_without_credentials_form():
    html = TestClient(app).get("/qa").text

    assert html.count("data-demo-account=") == 10
    assert 'id="auth-form"' not in html


def test_chat_storage_is_scoped_to_the_authenticated_user():
    script = TestClient(app).get("/static/js/app.js").text

    assert "`${CHAT_STORAGE_KEY}:${userId}`" in script
    assert "localStorage.setItem(\n      activeChatStorageKey," in script


def test_ui_renders_only_assistant_markdown_with_sanitization():
    client = TestClient(app)

    html = client.get("/qa").text
    script = client.get("/static/js/app.js").text

    assert html.index("marked@18.0.6") < html.index("dompurify@3.4.12") < html.index("app.js?v=10")
    assert "DOMPurify.sanitize" in script
    assert "formatAssistantAnswer(msg.text)" in script
    assert 'msg-bubble-user">${formatAnswerText(msg.text)}' in script


def test_documents_defaults_to_credit_agent_list():
    client = TestClient(app)

    html = client.get("/documents").text
    script = client.get("/static/js/app.js").text

    assert "Agent Credit · Đang tải danh sách" in html
    assert "const DEFAULT_DOCUMENT_AGENT_ID = 'credit';" in script
    assert "selectedAgentId: DEFAULT_DOCUMENT_AGENT_ID" in script
    assert "function ensureDefaultDocumentsLoaded()" in script
    assert "if (!getStoredAccessToken())" in script
    assert "loadDocumentsForAgent(agentId);" in script
