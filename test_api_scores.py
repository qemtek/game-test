"""
Tests for PARE-34 (GET /api/scores), PARE-35 (POST /api/scores),
and PARE-36 (GET /api/health).

Acceptance criteria covered:
  PARE-34: GET /api/scores returns top-10 rows ordered by score DESC as a JSON array.
  PARE-35: POST /api/scores validates name/score, inserts, returns 201 with full row
           including created_at.
  PARE-36: GET /api/health returns {"status": "ok"} with HTTP 200.
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


# ===========================================================================
# PARE-36 — GET /api/health
# ===========================================================================

class TestApiHealth:
    def test_returns_200(self, client):
        """PARE-36: GET /api/health returns HTTP 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_returns_status_ok(self, client):
        """PARE-36: response body is exactly {"status": "ok"}."""
        resp = client.get("/api/health")
        assert resp.get_json() == {"status": "ok"}


# ===========================================================================
# PARE-37 — Paginated & Filtered Score List
# ===========================================================================

class TestGetScoresPaginated:
    def test_no_params_returns_first_ten(self, client):
        """PARE-37: no params → up to 10 rows by score DESC."""
        for i in range(15):
            post_score(client, f"P{i}", i + 1)
        rows = client.get("/api/scores").get_json()
        assert len(rows) == 10
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_limit_param(self, client):
        """PARE-37: ?limit=5 returns at most 5 rows."""
        for i in range(10):
            post_score(client, f"P{i}", i + 1)
        rows = client.get("/api/scores?limit=5").get_json()
        assert len(rows) == 5

    def test_limit_capped_at_100(self, client):
        """PARE-37: ?limit=200 is capped at 100."""
        for i in range(10):
            post_score(client, f"P{i}", i + 1)
        rows = client.get("/api/scores?limit=200").get_json()
        assert len(rows) <= 100

    def test_offset_param(self, client):
        """PARE-37: ?offset=5 skips first 5 results."""
        for i in range(10):
            post_score(client, f"P{i}", i + 1)
        all_rows = client.get("/api/scores?limit=100").get_json()
        offset_rows = client.get("/api/scores?offset=5&limit=100").get_json()
        assert offset_rows == all_rows[5:]

    def test_filter_by_name(self, client):
        """PARE-37: ?name=Alice returns only Alice's scores."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        post_score(client, "Bob", 300)
        rows = client.get("/api/scores?name=Alice").get_json()
        assert all(r["name"] == "Alice" for r in rows)
        assert len(rows) == 2

    def test_filter_by_name_and_limit(self, client):
        """PARE-37: ?name=Alice&limit=1 combination."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        rows = client.get("/api/scores?name=Alice&limit=1").get_json()
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"
        assert rows[0]["score"] == 300  # highest

    def test_invalid_limit_returns_400(self, client):
        """PARE-37: ?limit=abc → 400."""
        resp = client.get("/api/scores?limit=abc")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_invalid_offset_returns_400(self, client):
        """PARE-37: ?offset=abc → 400."""
        resp = client.get("/api/scores?offset=abc")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_float_limit_returns_400(self, client):
        """PARE-37: ?limit=1.5 → 400 (non-integer string)."""
        resp = client.get("/api/scores?limit=1.5")
        assert resp.status_code == 400

    def test_name_filter_case_sensitive(self, client):
        """PARE-37: name filter is case-sensitive."""
        post_score(client, "Alice", 100)
        rows = client.get("/api/scores?name=alice").get_json()
        assert rows == []


# ===========================================================================
# PARE-38 — Fetch Score by ID
# ===========================================================================

class TestGetScoreById:
    def test_valid_id_returns_200(self, client):
        """PARE-38: existing id → 200."""
        body = post_score(client, "Alice", 500).get_json()
        resp = client.get(f"/api/scores/{body['id']}")
        assert resp.status_code == 200

    def test_nonexistent_id_returns_404(self, client):
        """PARE-38: non-existent id → 404."""
        resp = client.get("/api/scores/9999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_returned_fields(self, client):
        """PARE-38: response has id, name, score, created_at."""
        body = post_score(client, "Bob", 750).get_json()
        row = client.get(f"/api/scores/{body['id']}").get_json()
        assert set(row.keys()) == {"id", "name", "score", "created_at"}

    def test_values_match_insert(self, client):
        """PARE-38: returned values match what was inserted."""
        inserted = post_score(client, "Charlie", 999).get_json()
        fetched = client.get(f"/api/scores/{inserted['id']}").get_json()
        assert fetched["name"] == "Charlie"
        assert fetched["score"] == 999
        assert fetched["id"] == inserted["id"]

    def test_retrieve_multiple_by_id(self, client):
        """PARE-38: retrieve each of multiple inserts by its id."""
        ids = []
        for name, score in [("Alice", 100), ("Bob", 200)]:
            ids.append(post_score(client, name, score).get_json()["id"])
        row0 = client.get(f"/api/scores/{ids[0]}").get_json()
        row1 = client.get(f"/api/scores/{ids[1]}").get_json()
        assert row0["name"] == "Alice"
        assert row1["name"] == "Bob"


# ===========================================================================
# PARE-39 — Player List
# ===========================================================================

class TestGetPlayers:
    def test_empty_db_returns_empty_list(self, client):
        """PARE-39: no scores → []."""
        resp = client.get("/api/players")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_single_player_multiple_games(self, client):
        """PARE-39: single player stats are correct."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        rows = client.get("/api/players").get_json()
        assert len(rows) == 1
        p = rows[0]
        assert p["name"] == "Alice"
        assert p["best_score"] == 300
        assert p["total_games"] == 3
        assert isinstance(p["avg_score"], (int, float))
        assert abs(p["avg_score"] - 200.0) < 0.01

    def test_multiple_players_ordered_by_best_score(self, client):
        """PARE-39: multiple players ordered best_score DESC."""
        post_score(client, "Charlie", 500)
        post_score(client, "Alice", 1000)
        post_score(client, "Bob", 750)
        rows = client.get("/api/players").get_json()
        best_scores = [r["best_score"] for r in rows]
        assert best_scores == sorted(best_scores, reverse=True)
        assert rows[0]["name"] == "Alice"

    def test_response_fields(self, client):
        """PARE-39: each entry has name, best_score, total_games, avg_score."""
        post_score(client, "Alice", 100)
        rows = client.get("/api/players").get_json()
        assert set(rows[0].keys()) == {"name", "best_score", "total_games", "avg_score"}

    def test_avg_score_is_numeric(self, client):
        """PARE-39: avg_score is int or float."""
        post_score(client, "Alice", 100)
        rows = client.get("/api/players").get_json()
        assert isinstance(rows[0]["avg_score"], (int, float))


# ===========================================================================
# PARE-40 — Player Profile
# ===========================================================================

class TestGetPlayerProfile:
    def test_unknown_player_returns_404(self, client):
        """PARE-40: unknown name → 404."""
        resp = client.get("/api/players/Nobody")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_single_player_rank_1(self, client):
        """PARE-40: only player in DB gets rank 1."""
        post_score(client, "Alice", 500)
        profile = client.get("/api/players/Alice").get_json()
        assert profile["rank"] == 1

    def test_profile_fields(self, client):
        """PARE-40: response has expected top-level fields."""
        post_score(client, "Alice", 500)
        profile = client.get("/api/players/Alice").get_json()
        assert set(profile.keys()) == {"name", "rank", "best_score", "avg_score", "total_games", "recent_scores"}

    def test_rank_ordering(self, client):
        """PARE-40: rank=1 for top player, rank=2 for second-best."""
        post_score(client, "Alice", 1000)
        post_score(client, "Bob", 500)
        alice = client.get("/api/players/Alice").get_json()
        bob = client.get("/api/players/Bob").get_json()
        assert alice["rank"] == 1
        assert bob["rank"] == 2

    def test_recent_scores_capped_at_10(self, client):
        """PARE-40: recent_scores has at most 10 entries."""
        for i in range(15):
            post_score(client, "Alice", i + 1)
        profile = client.get("/api/players/Alice").get_json()
        assert len(profile["recent_scores"]) <= 10

    def test_recent_scores_no_name_field(self, client):
        """PARE-40: recent_scores entries have id, score, created_at — no name."""
        post_score(client, "Alice", 100)
        profile = client.get("/api/players/Alice").get_json()
        for entry in profile["recent_scores"]:
            assert set(entry.keys()) == {"id", "score", "created_at"}

    def test_stats_correct(self, client):
        """PARE-40: best_score, total_games, avg_score are correct."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        profile = client.get("/api/players/Alice").get_json()
        assert profile["best_score"] == 300
        assert profile["total_games"] == 3
        assert isinstance(profile["avg_score"], (int, float))
        assert abs(profile["avg_score"] - 200.0) < 0.01

    def test_tied_best_score_same_rank(self, client):
        """PARE-40: players with the same best score share the same rank."""
        post_score(client, "Alice", 500)
        post_score(client, "Bob", 500)
        alice = client.get("/api/players/Alice").get_json()
        bob = client.get("/api/players/Bob").get_json()
        assert alice["rank"] == bob["rank"]

    def test_recent_scores_ordered_by_created_at_desc(self, client):
        """PARE-40: recent_scores are ordered created_at DESC (latest first, ties allowed)."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        profile = client.get("/api/players/Alice").get_json()
        recent = profile["recent_scores"]
        assert len(recent) == 3
        # created_at values must be non-increasing (DESC with possible ties)
        timestamps = [r["created_at"] for r in recent]
        assert timestamps == sorted(timestamps, reverse=True)
