from pathlib import Path

from app.auth.passwords import verify_password
from app.auth.service import provision_user
from app.auth.tokens import hash_token
from app.db.models import AuthSession, User
from app.db.session import reset_database_state, session_scope
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.conftest import make_app, make_client
from tests.sql_support import create_catalog_database

EMAIL = "beta@predicta.test"
PASSWORD = "correct-horse-battery"
AUTH_DIR = Path(__file__).resolve().parents[1] / "app" / "auth"


def _client(tmp_path: Path, *, client_base_url: str = "http://testserver", **overrides: object):
    url = create_catalog_database(tmp_path / "auth.sqlite", seed=False)
    values = {
        "auth_bypass": False,
        "database_url": url,
        "invite_allowlist": [EMAIL],
        "cors_origins": ["http://localhost:3000"],
    }
    values.update(overrides)
    app = make_app(**values)
    with session_scope(app.state.settings) as session:
        provision_user(session, email=EMAIL, password=PASSWORD, now=app.state.container.clock.now())
    return TestClient(app, base_url=client_base_url)


def _login(client, *, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_health_stays_public_when_auth_is_on(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"
        ready = client.get("/ready")
        assert ready.status_code == 200
    finally:
        reset_database_state()


def test_protected_product_api_returns_honest_401(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        response = client.get("/api/v1/matches")
        assert response.status_code == 401
        body = response.json()
        assert body["title"] == "Unauthorized"
        assert body["type"] == "/problems/unauthorized"
        assert "request_id" in body
        assert client.get("/api/v1/dashboard").status_code == 401
        assert client.get("/api/v1/picks").status_code == 401
    finally:
        reset_database_state()


def test_login_sets_httponly_session_and_readable_csrf(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        response = _login(client)
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["user"]["email"] == EMAIL
        csrf = payload["csrf_token"]
        assert len(csrf) >= 16
        cookies = response.headers.get_list("set-cookie")
        session_header = next(item for item in cookies if item.startswith("predicta_session="))
        csrf_header = next(item for item in cookies if item.startswith("predicta_csrf="))
        assert "httponly" in session_header.lower()
        assert "samesite=lax" in session_header.lower()
        assert "secure" not in session_header.lower()
        assert "httponly" not in csrf_header.lower()
        assert client.cookies.get("predicta_session")
        assert client.cookies.get("predicta_csrf") == csrf
        assert client.cookies.get("predicta_session").count(".") != 2
        matches = client.get("/api/v1/matches")
        assert matches.status_code == 200
        assert matches.json()["data_mode"] == "mock"
    finally:
        reset_database_state()


def test_session_hash_is_stored_not_the_raw_token(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        _login(client)
        raw = client.cookies.get("predicta_session")
        assert raw
        settings = client.app.state.settings
        with session_scope(settings) as session:
            rows = list(session.scalars(select(AuthSession)))
            users = list(session.scalars(select(User)))
            assert len(rows) == 1
            assert raw not in {row.token_hash for row in rows}
            assert raw not in {row.csrf_token_hash for row in rows}
            assert rows[0].token_hash == hash_token(raw)
            assert users[0].password_hash.startswith("$argon2id$")
            assert PASSWORD not in users[0].password_hash
            assert verify_password(users[0].password_hash, PASSWORD)
    finally:
        reset_database_state()


def test_login_rejects_unknown_and_non_allowlisted_users(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        unknown = _login(client, email="nobody@predicta.test")
        assert unknown.status_code == 401
        assert unknown.json()["detail"] == "Invalid email or password."
        wrong = _login(client, password="wrong-password")
        assert wrong.status_code == 401
    finally:
        reset_database_state()


def test_analyze_requires_csrf_header_matching_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        login = _login(client)
        csrf = login.json()["data"]["csrf_token"]
        body = {"match_id": "mth_northgate_harbor", "question": None}
        missing = client.post("/api/v1/ai/analyze", json=body)
        assert missing.status_code == 403
        assert missing.json()["type"] == "/problems/forbidden"
        wrong = client.post("/api/v1/ai/analyze", json=body, headers={"X-CSRF-Token": "a" * 32})
        assert wrong.status_code == 403
        ok = client.post("/api/v1/ai/analyze", json=body, headers={"X-CSRF-Token": csrf})
        assert ok.status_code == 200
        assert ok.json()["data"]["match_id"] == "mth_northgate_harbor"
    finally:
        reset_database_state()


def test_logout_revokes_session_and_requires_csrf(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        login = _login(client)
        csrf = login.json()["data"]["csrf_token"]
        denied = client.post("/api/v1/auth/logout")
        assert denied.status_code == 403
        ok = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        assert ok.status_code == 200
        assert ok.json()["data"]["logged_out"] is True
        assert client.get("/api/v1/matches").status_code == 401
        assert client.get("/api/v1/auth/session").status_code == 401
    finally:
        reset_database_state()


def test_session_probe_and_bypass_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        anonymous = client.get("/api/v1/auth/session")
        assert anonymous.status_code == 401
        _login(client)
        session = client.get("/api/v1/auth/session")
        assert session.status_code == 200
        assert session.json()["data"]["user"]["email"] == EMAIL
        assert session.json()["data"]["bypass"] is False
    finally:
        reset_database_state()


def test_auth_bypass_client_skips_login() -> None:
    client = make_client()
    assert client.get("/api/v1/matches").status_code == 200
    body = client.get("/api/v1/auth/session").json()["data"]
    assert body["user"] is None
    assert body["bypass"] is True


def test_staging_disables_docs_and_requires_auth(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        env="staging",
        repository="sql",
        data_mode="live",
        cors_origins=["https://web.staging.example.com"],
        client_base_url="https://testserver",
    )
    try:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/matches").status_code == 401
        login = _login(client)
        assert login.status_code == 200
        cookies = login.headers.get_list("set-cookie")
        session_header = next(item for item in cookies if item.startswith("predicta_session="))
        assert "Secure" in session_header
        assert "HttpOnly" in session_header
        assert "samesite=lax" in session_header.lower()
        csrf = login.json()["data"]["csrf_token"]
        matches = client.get("/api/v1/matches")
        assert matches.status_code == 200
        assert matches.json()["data_mode"] == "live"
        analyze = client.post(
            "/api/v1/ai/analyze",
            json={"match_id": "mth_missing", "question": None},
            headers={"X-CSRF-Token": csrf},
        )
        assert analyze.status_code in {403, 404}
    finally:
        reset_database_state()


def test_auth_code_does_not_use_jwt() -> None:
    for path in AUTH_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "jwt" not in text
        assert "pyjwt" not in text
        assert "localstorage" not in text


def test_alembic_users_sessions_stores_token_hash() -> None:
    migration = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0005_users_sessions.py"
    ).read_text(encoding="utf-8")
    assert "token_hash" in migration
    assert "password_hash" in migration
    assert "create_table(\n        \"users\"" in migration or 'create_table(\n        "users"' in migration
    assert "sessions" in migration
    assert "jwt" not in migration.lower()
