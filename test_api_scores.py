"""
Tests for PARE-34 (GET /api/scores) and PARE-35 (POST /api/scores).

Acceptance criteria covered:
  PARE-34: GET /api/scores returns top-10 rows ordered by score DESC as a JSON array.
  PARE-35: POST /api/scores validates name/score, inserts, returns 201 with full row
           including created_at.
"""

import os
import json
import pytest
import tempfile

# Use an isolated in-memory/temp DB for every test run
import database  # noqa: E402 — must happen before importing app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point database.DB_PATH at a fresh temporary file for each test."""
    db_file = tmp_path / "test_scores.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    # Also propagate to the env var path used by sqlite3.connect inside get_db
    monkeypatch.setenv("DB_PATH", str(db_file))
    database.init_db()
    yield


@pytest.fixture()
def client(isolated_db):
    import app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def post_score(client, name, score, content_type="application/json"):
    return client.post(
        "/api/scores",
        data=json.dumps({"name": name, "score": score}),
        content_type=content_type,
    )


# ===========================================================================
# PARE-34 — GET /api/scores
# ===========================================================================

class TestGetScores:
    def test_empty_returns_empty_list(self, client):
        """PARE-34: fresh DB returns an empty array, not an error."""
        resp = client.get("/api/scores")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_json_content_type(self, client):
        """PARE-34: Content-Type must be application/json."""
        resp = client.get("/api/scores")
        assert "application/json" in resp.content_type

    def test_returns_rows_with_expected_fields(self, client):
        """PARE-34: each row contains id, name, score, created_at."""
        post_score(client, "Alice", 100)
        resp = client.get("/api/scores")
        rows = resp.get_json()
        assert len(rows) == 1
        assert set(rows[0].keys()) == {"id", "name", "score", "created_at"}

    def test_ordered_by_score_desc(self, client):
        """PARE-34: rows are ordered highest score first."""
        for name, score in [("C", 300), ("A", 100), ("B", 200)]:
            post_score(client, name, score)
        rows = client.get("/api/scores").get_json()
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_limit_ten(self, client):
        """PARE-34: no more than 10 rows returned even when DB has more."""
        for i in range(15):
            post_score(client, f"Player{i}", i + 1)
        rows = client.get("/api/scores").get_json()
        assert len(rows) <= 10

    def test_limit_returns_top_ten_highest(self, client):
        """PARE-34: the 10 rows returned are the highest 10 scores."""
        for i in range(15):
            post_score(client, f"P{i}", i + 1)
        rows = client.get("/api/scores").get_json()
        returned_scores = sorted([r["score"] for r in rows], reverse=True)
        expected = list(range(15, 5, -1))  # 15 down to 6
        assert returned_scores == expected

    def test_exactly_ten_rows(self, client):
        """PARE-34: exactly 10 inserts → exactly 10 rows returned."""
        for i in range(10):
            post_score(client, f"P{i}", i + 1)
        rows = client.get("/api/scores").get_json()
        assert len(rows) == 10

    def test_created_at_is_string(self, client):
        """PARE-34: created_at is returned as a raw SQLite string."""
        post_score(client, "Alice", 42)
        rows = client.get("/api/scores").get_json()
        assert isinstance(rows[0]["created_at"], str)

    def test_id_is_integer(self, client):
        """PARE-34: id field is a JSON integer."""
        post_score(client, "Alice", 42)
        rows = client.get("/api/scores").get_json()
        assert isinstance(rows[0]["id"], int)


# ===========================================================================
# PARE-35 — POST /api/scores
# ===========================================================================

class TestPostScore:
    # ---- Happy path --------------------------------------------------------

    def test_returns_201(self, client):
        """PARE-35: successful POST returns HTTP 201."""
        resp = post_score(client, "Alice", 1500)
        assert resp.status_code == 201

    def test_response_contains_expected_fields(self, client):
        """PARE-35: response body has id, name, score, created_at."""
        body = post_score(client, "Alice", 1500).get_json()
        assert set(body.keys()) == {"id", "name", "score", "created_at"}

    def test_response_name_matches_input(self, client):
        """PARE-35: returned name equals the submitted (stripped) name."""
        body = post_score(client, "Alice", 1500).get_json()
        assert body["name"] == "Alice"

    def test_response_score_matches_input(self, client):
        """PARE-35: returned score equals the submitted score."""
        body = post_score(client, "Alice", 1500).get_json()
        assert body["score"] == 1500

    def test_response_id_is_integer(self, client):
        """PARE-35: returned id is an integer."""
        body = post_score(client, "Alice", 1500).get_json()
        assert isinstance(body["id"], int)

    def test_response_created_at_is_string(self, client):
        """PARE-35: created_at is a string (raw SQLite timestamp)."""
        body = post_score(client, "Alice", 1500).get_json()
        assert isinstance(body["created_at"], str)

    def test_score_persists_in_db(self, client):
        """PARE-35: inserted score is retrievable via GET /api/scores."""
        post_score(client, "Alice", 9999)
        rows = client.get("/api/scores").get_json()
        assert any(r["name"] == "Alice" and r["score"] == 9999 for r in rows)

    def test_name_is_stripped(self, client):
        """PARE-35: leading/trailing whitespace is stripped before insertion."""
        body = post_score(client, "  Bob  ", 100).get_json()
        assert body["name"] == "Bob"

    # ---- Invalid JSON body -------------------------------------------------

    def test_non_json_body_returns_400(self, client):
        """PARE-35: non-JSON body → 400."""
        resp = client.post(
            "/api/scores",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_wrong_content_type_returns_400(self, client):
        """PARE-35: form-encoded body (no JSON) → 400 (silent=True returns None)."""
        resp = client.post(
            "/api/scores",
            data={"name": "Alice", "score": "100"},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400

    def test_error_body_shape_on_bad_json(self, client):
        """PARE-35: error response shape is {"error": "..."}."""
        resp = client.post(
            "/api/scores",
            data="not json",
            content_type="application/json",
        )
        body = resp.get_json()
        assert "error" in body

    # ---- Name validation ---------------------------------------------------

    def test_missing_name_returns_422(self, client):
        """PARE-35: omitting name key → 422."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"score": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_empty_string_name_returns_422(self, client):
        """PARE-35: empty string name → 422."""
        resp = post_score(client, "", 100)
        assert resp.status_code == 422

    def test_whitespace_only_name_returns_422(self, client):
        """PARE-35: whitespace-only name → 422."""
        resp = post_score(client, "   ", 100)
        assert resp.status_code == 422

    def test_numeric_name_returns_422(self, client):
        """PARE-35: integer as name → 422."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": 123, "score": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_null_name_returns_422(self, client):
        """PARE-35: null name → 422."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": None, "score": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    # ---- Score validation --------------------------------------------------

    def test_missing_score_returns_422(self, client):
        """PARE-35: omitting score key → 422."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": "Alice"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_zero_score_returns_422(self, client):
        """PARE-35: score=0 is not positive → 422."""
        resp = post_score(client, "Alice", 0)
        assert resp.status_code == 422

    def test_negative_score_returns_422(self, client):
        """PARE-35: negative score → 422."""
        resp = post_score(client, "Alice", -1)
        assert resp.status_code == 422

    def test_float_score_returns_422(self, client):
        """PARE-35: float score → 422 (must be int)."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": "Alice", "score": 1.5}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_string_score_returns_422(self, client):
        """PARE-35: string score → 422."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": "Alice", "score": "100"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_null_score_returns_422(self, client):
        """PARE-35: null score → 422."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": "Alice", "score": None}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_bool_true_score_returns_422(self, client):
        """PARE-35: bool True must be rejected (bool is subclass of int)."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": "Alice", "score": True}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_bool_false_score_returns_422(self, client):
        """PARE-35: bool False must be rejected."""
        resp = client.post(
            "/api/scores",
            data=json.dumps({"name": "Alice", "score": False}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    # ---- Error body shape --------------------------------------------------

    def test_error_body_shape_on_bad_name(self, client):
        """PARE-35: error body is {"error": "..."} on name validation failure."""
        resp = post_score(client, "", 100)
        body = resp.get_json()
        assert "error" in body
        assert isinstance(body["error"], str)

    def test_error_body_shape_on_bad_score(self, client):
        """PARE-35: error body is {"error": "..."} on score validation failure."""
        resp = post_score(client, "Alice", -5)
        body = resp.get_json()
        assert "error" in body
        assert isinstance(body["error"], str)

    # ---- Multiple inserts --------------------------------------------------

    def test_multiple_inserts_get_unique_ids(self, client):
        """PARE-35: each POST returns a distinct id."""
        id1 = post_score(client, "Alice", 100).get_json()["id"]
        id2 = post_score(client, "Bob", 200).get_json()["id"]
        assert id1 != id2
