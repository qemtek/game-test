"""
Tests for PARE-36 — GET /api/health endpoint.

Acceptance criteria:
  - Route exists at GET /api/health
  - Returns HTTP 200
  - Returns JSON body {"status": "ok"}
  - Does not affect existing routes
"""

import json
import pytest
import database


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Isolated DB for each test (consistent with rest of suite)."""
    db_file = tmp_path / "test_scores.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    monkeypatch.setenv("DB_PATH", str(db_file))
    database.init_db()
    yield


@pytest.fixture()
def client(isolated_db):
    import app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


# ===========================================================================
# PARE-36 — GET /api/health
# ===========================================================================

class TestApiHealth:
    def test_returns_200(self, client):
        """PARE-36: GET /api/health returns HTTP 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_returns_json_content_type(self, client):
        """PARE-36: response Content-Type is application/json."""
        resp = client.get("/api/health")
        assert "application/json" in resp.content_type

    def test_body_is_status_ok(self, client):
        """PARE-36: response body is exactly {"status": "ok"}."""
        resp = client.get("/api/health")
        assert resp.get_json() == {"status": "ok"}

    def test_status_value_is_string_ok(self, client):
        """PARE-36: body["status"] is the string "ok"."""
        body = client.get("/api/health").get_json()
        assert body.get("status") == "ok"

    def test_no_extra_fields(self, client):
        """PARE-36: body contains only the 'status' key (no version or extras)."""
        body = client.get("/api/health").get_json()
        assert set(body.keys()) == {"status"}

    def test_post_not_allowed(self, client):
        """PARE-36: /api/health does not accept POST (405 Method Not Allowed)."""
        resp = client.post("/api/health", json={})
        assert resp.status_code == 405

    # ---- Existing routes unaffected ----------------------------------------

    def test_root_health_still_works(self, client):
        """PARE-36: pre-existing /health route still returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_root_health_still_has_version(self, client):
        """PARE-36: /health still returns version field (unchanged)."""
        body = client.get("/health").get_json()
        assert "version" in body

    def test_get_scores_still_works(self, client):
        """PARE-36: GET /api/scores still returns 200 after adding /api/health."""
        resp = client.get("/api/scores")
        assert resp.status_code == 200
