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


# ===========================================================================
# Helpers for tournament tests
# ===========================================================================

from datetime import datetime, timezone, timedelta


def future_ts(seconds=3600):
    """Return an ISO8601 UTC timestamp N seconds in the future."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def past_ts(seconds=3600):
    """Return an ISO8601 UTC timestamp N seconds in the past."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def create_tournament(client, name="Test Cup", starts_offset=3600, ends_offset=7200):
    """Create a tournament and return the response."""
    return client.post("/api/tournaments", json={
        "name": name,
        "starts_at": future_ts(starts_offset),
        "ends_at": future_ts(ends_offset),
    })


def create_active_tournament(client, name="Active Cup"):
    """Create a tournament that is already active (starts_at in the past)."""
    return client.post("/api/tournaments", json={
        "name": name,
        "starts_at": future_ts(1),   # just 1 second ahead — will appear open at creation
        "ends_at": future_ts(7200),
    })


def create_tournament_raw(client, payload):
    """Create a tournament with a raw payload dict."""
    return client.post("/api/tournaments", json=payload)


def join_tournament(client, tournament_id, name="Alice"):
    return client.post(f"/api/tournaments/{tournament_id}/join", json={"name": name})


def submit_score(client, tournament_id, name, score):
    return client.post(f"/api/tournaments/{tournament_id}/score", json={"name": name, "score": score})


# ===========================================================================
# PARE-41/42 — POST /api/tournaments (create)
# ===========================================================================

class TestCreateTournament:
    def test_create_returns_201(self, client):
        """PARE-42: successful creation returns 201."""
        resp = create_tournament(client)
        assert resp.status_code == 201

    def test_create_response_fields(self, client):
        """PARE-42: response contains all expected fields."""
        resp = create_tournament(client, name="Spring Cup")
        data = resp.get_json()
        assert set(data.keys()) == {"id", "name", "status", "starts_at", "ends_at", "created_at"}

    def test_create_status_is_open(self, client):
        """PARE-42: new tournament starts with status='open'."""
        data = create_tournament(client).get_json()
        assert data["status"] == "open"

    def test_create_name_stored(self, client):
        """PARE-42: name is stored correctly."""
        data = create_tournament(client, name="My Cup").get_json()
        assert data["name"] == "My Cup"

    def test_create_id_is_integer(self, client):
        """PARE-42: id is an integer."""
        data = create_tournament(client).get_json()
        assert isinstance(data["id"], int)

    def test_create_missing_name_returns_400(self, client):
        """PARE-42: missing name → 400."""
        resp = create_tournament_raw(client, {
            "starts_at": future_ts(3600),
            "ends_at": future_ts(7200),
        })
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_empty_name_returns_400(self, client):
        """PARE-42: empty name → 400."""
        resp = create_tournament_raw(client, {
            "name": "   ",
            "starts_at": future_ts(3600),
            "ends_at": future_ts(7200),
        })
        assert resp.status_code == 400

    def test_create_missing_starts_at_returns_400(self, client):
        """PARE-42: missing starts_at → 400."""
        resp = create_tournament_raw(client, {
            "name": "Cup",
            "ends_at": future_ts(7200),
        })
        assert resp.status_code == 400

    def test_create_missing_ends_at_returns_400(self, client):
        """PARE-42: missing ends_at → 400."""
        resp = create_tournament_raw(client, {
            "name": "Cup",
            "starts_at": future_ts(3600),
        })
        assert resp.status_code == 400

    def test_create_ends_before_starts_returns_400(self, client):
        """PARE-42: ends_at <= starts_at → 400."""
        resp = create_tournament_raw(client, {
            "name": "Cup",
            "starts_at": future_ts(7200),
            "ends_at": future_ts(3600),
        })
        assert resp.status_code == 400

    def test_create_starts_in_past_returns_400(self, client):
        """PARE-42: starts_at in the past → 400."""
        resp = create_tournament_raw(client, {
            "name": "Cup",
            "starts_at": past_ts(3600),
            "ends_at": future_ts(7200),
        })
        assert resp.status_code == 400

    def test_create_no_body_returns_400(self, client):
        """PARE-42: no JSON body → 400."""
        resp = client.post("/api/tournaments", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_create_multiple_get_distinct_ids(self, client):
        """PARE-42: each tournament gets a unique id."""
        id1 = create_tournament(client, name="Cup 1").get_json()["id"]
        id2 = create_tournament(client, name="Cup 2").get_json()["id"]
        assert id1 != id2


# ===========================================================================
# PARE-43 — GET /api/tournaments (list with dynamic status)
# ===========================================================================

class TestListTournaments:
    def test_empty_list(self, client):
        """PARE-43: no tournaments → empty array."""
        resp = client.get("/api/tournaments")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_contains_created_tournament(self, client):
        """PARE-43: newly created tournament appears in list."""
        create_tournament(client, name="Spring Cup")
        data = client.get("/api/tournaments").get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Spring Cup"

    def test_list_ordered_starts_at_desc(self, client):
        """PARE-43: tournaments are ordered by starts_at DESC."""
        create_tournament(client, name="Early", starts_offset=3600, ends_offset=7200)
        create_tournament(client, name="Late", starts_offset=7200, ends_offset=10800)
        data = client.get("/api/tournaments").get_json()
        starts = [t["starts_at"] for t in data]
        assert starts == sorted(starts, reverse=True)

    def test_list_status_filter_open(self, client):
        """PARE-43: ?status=open filters correctly."""
        create_tournament(client, name="Open Cup")
        data = client.get("/api/tournaments?status=open").get_json()
        assert all(t["status"] == "open" for t in data)
        assert len(data) >= 1

    def test_list_status_filter_excludes_others(self, client):
        """PARE-43: ?status=completed returns empty when only open tournaments exist."""
        create_tournament(client, name="Open Cup")
        data = client.get("/api/tournaments?status=completed").get_json()
        assert data == []

    def test_list_response_fields(self, client):
        """PARE-43: each entry has the expected fields."""
        create_tournament(client)
        data = client.get("/api/tournaments").get_json()
        assert set(data[0].keys()) == {"id", "name", "status", "starts_at", "ends_at", "created_at"}

    def test_list_no_standings_field(self, client):
        """PARE-43: list endpoint does NOT include standings."""
        create_tournament(client)
        data = client.get("/api/tournaments").get_json()
        assert "standings" not in data[0]


# ===========================================================================
# PARE-44 — POST /api/tournaments/<id>/join
# ===========================================================================

class TestJoinTournament:
    def test_join_open_tournament_returns_201(self, client):
        """PARE-44: joining an open tournament returns 201."""
        t = create_tournament(client).get_json()
        resp = join_tournament(client, t["id"])
        assert resp.status_code == 201

    def test_join_response_fields(self, client):
        """PARE-44: join response has expected fields."""
        t = create_tournament(client).get_json()
        entry = join_tournament(client, t["id"]).get_json()
        assert set(entry.keys()) == {"id", "tournament_id", "name", "best_score", "submitted_at", "joined_at"}

    def test_join_best_score_null(self, client):
        """PARE-44: best_score is null on initial join."""
        t = create_tournament(client).get_json()
        entry = join_tournament(client, t["id"]).get_json()
        assert entry["best_score"] is None

    def test_join_idempotent_returns_200(self, client):
        """PARE-44: re-joining returns 200 with same entry."""
        t = create_tournament(client).get_json()
        first = join_tournament(client, t["id"], "Alice").get_json()
        second = join_tournament(client, t["id"], "Alice")
        assert second.status_code == 200
        assert second.get_json()["id"] == first["id"]

    def test_join_different_players(self, client):
        """PARE-44: two different players get distinct entries."""
        t = create_tournament(client).get_json()
        e1 = join_tournament(client, t["id"], "Alice").get_json()
        e2 = join_tournament(client, t["id"], "Bob").get_json()
        assert e1["id"] != e2["id"]
        assert e1["name"] == "Alice"
        assert e2["name"] == "Bob"

    def test_join_not_found_returns_404(self, client):
        """PARE-44: joining non-existent tournament → 404."""
        resp = join_tournament(client, 9999)
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_join_completed_tournament_returns_422(self, client):
        """PARE-44: joining a completed tournament → 422."""
        # Create tournament with starts_at/ends_at in the past so it can be completed
        import database as db
        t_resp = create_tournament(client).get_json()
        tid = t_resp["id"]
        # Force status to completed in DB
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='completed' WHERE id=?", (tid,))
            conn.commit()
        resp = join_tournament(client, tid)
        assert resp.status_code == 422

    def test_join_missing_name_returns_400(self, client):
        """PARE-44: missing name field → 400."""
        t = create_tournament(client).get_json()
        resp = client.post(f"/api/tournaments/{t['id']}/join", json={})
        assert resp.status_code == 400

    def test_join_empty_name_returns_400(self, client):
        """PARE-44: empty name → 400."""
        t = create_tournament(client).get_json()
        resp = client.post(f"/api/tournaments/{t['id']}/join", json={"name": "  "})
        assert resp.status_code == 400


# ===========================================================================
# PARE-45 — POST /api/tournaments/<id>/score
# ===========================================================================

class TestSubmitTournamentScore:
    def _setup_active(self, client):
        """Create an active tournament and join Alice."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        # Force to active
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        return tid

    def test_submit_score_returns_200(self, client):
        """PARE-45: valid score submission returns 200."""
        tid = self._setup_active(client)
        resp = submit_score(client, tid, "Alice", 1000)
        assert resp.status_code == 200

    def test_submit_score_updates_best_score(self, client):
        """PARE-45: best_score is updated after first submission."""
        tid = self._setup_active(client)
        entry = submit_score(client, tid, "Alice", 1000).get_json()
        assert entry["best_score"] == 1000

    def test_submit_higher_score_updates(self, client):
        """PARE-45: submitting a higher score updates best_score."""
        tid = self._setup_active(client)
        submit_score(client, tid, "Alice", 1000)
        entry = submit_score(client, tid, "Alice", 2000).get_json()
        assert entry["best_score"] == 2000

    def test_submit_lower_score_no_update(self, client):
        """PARE-45: submitting a lower score does NOT update best_score."""
        tid = self._setup_active(client)
        submit_score(client, tid, "Alice", 2000)
        entry = submit_score(client, tid, "Alice", 500).get_json()
        assert entry["best_score"] == 2000

    def test_submit_score_response_fields(self, client):
        """PARE-45: response has entry fields."""
        tid = self._setup_active(client)
        entry = submit_score(client, tid, "Alice", 500).get_json()
        assert set(entry.keys()) == {"id", "tournament_id", "name", "best_score", "submitted_at", "joined_at"}

    def test_submit_score_not_joined_returns_409(self, client):
        """PARE-45: player not joined → 409."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        resp = submit_score(client, tid, "Ghost", 500)
        assert resp.status_code == 409

    def test_submit_score_open_tournament_returns_422(self, client):
        """PARE-45: submitting to open tournament → 422."""
        t = create_tournament(client).get_json()
        join_tournament(client, t["id"], "Alice")
        resp = submit_score(client, t["id"], "Alice", 500)
        assert resp.status_code == 422

    def test_submit_score_completed_tournament_returns_422(self, client):
        """PARE-45: submitting to completed tournament → 422."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        join_tournament(client, tid, "Alice")
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='completed' WHERE id=?", (tid,))
            conn.commit()
        resp = submit_score(client, tid, "Alice", 500)
        assert resp.status_code == 422

    def test_submit_score_negative_returns_422(self, client):
        """PARE-45: negative score → 422."""
        tid = self._setup_active(client)
        resp = submit_score(client, tid, "Alice", -100)
        assert resp.status_code == 422

    def test_submit_score_zero_returns_422(self, client):
        """PARE-45: zero score → 422."""
        tid = self._setup_active(client)
        resp = submit_score(client, tid, "Alice", 0)
        assert resp.status_code == 422

    def test_submit_score_bool_returns_422(self, client):
        """PARE-45: boolean score → 422."""
        tid = self._setup_active(client)
        resp = client.post(f"/api/tournaments/{tid}/score", json={"name": "Alice", "score": True})
        assert resp.status_code == 422

    def test_submit_score_not_found_returns_404(self, client):
        """PARE-45: non-existent tournament → 404."""
        resp = submit_score(client, 9999, "Alice", 500)
        assert resp.status_code == 404

    def test_submit_equal_score_no_update(self, client):
        """PARE-45: submitting equal score does not increase best_score."""
        tid = self._setup_active(client)
        submit_score(client, tid, "Alice", 1000)
        entry = submit_score(client, tid, "Alice", 1000).get_json()
        assert entry["best_score"] == 1000


# ===========================================================================
# PARE-46 — GET /api/tournaments/<id> (detail + standings)
# ===========================================================================

class TestGetTournament:
    def test_get_not_found_returns_404(self, client):
        """PARE-46: non-existent tournament → 404."""
        resp = client.get("/api/tournaments/9999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_get_response_fields(self, client):
        """PARE-46: response has top-level fields including standings."""
        t = create_tournament(client).get_json()
        data = client.get(f"/api/tournaments/{t['id']}").get_json()
        assert set(data.keys()) == {"id", "name", "status", "starts_at", "ends_at", "created_at", "standings"}

    def test_get_standings_empty_no_players(self, client):
        """PARE-46: standings is empty list when no players joined."""
        t = create_tournament(client).get_json()
        data = client.get(f"/api/tournaments/{t['id']}").get_json()
        assert data["standings"] == []

    def test_get_standings_with_players(self, client):
        """PARE-46: standings includes joined players."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        join_tournament(client, tid, "Bob")
        submit_score(client, tid, "Alice", 1500)
        submit_score(client, tid, "Bob", 1200)
        data = client.get(f"/api/tournaments/{tid}").get_json()
        assert len(data["standings"]) == 2

    def test_get_standings_ordered_by_score_desc(self, client):
        """PARE-46: standings ordered best_score DESC."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        join_tournament(client, tid, "Bob")
        submit_score(client, tid, "Alice", 1500)
        submit_score(client, tid, "Bob", 1200)
        data = client.get(f"/api/tournaments/{tid}").get_json()
        scores = [s["best_score"] for s in data["standings"] if s["best_score"] is not None]
        assert scores == sorted(scores, reverse=True)
        assert data["standings"][0]["name"] == "Alice"

    def test_get_standings_null_scores_last(self, client):
        """PARE-46: players without scores appear last in standings."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        join_tournament(client, tid, "NoScore")
        submit_score(client, tid, "Alice", 1000)
        data = client.get(f"/api/tournaments/{tid}").get_json()
        standings = data["standings"]
        assert standings[0]["name"] == "Alice"
        assert standings[-1]["best_score"] is None

    def test_get_standings_rank_field(self, client):
        """PARE-46: each standing entry has a rank field starting at 1."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        submit_score(client, tid, "Alice", 1000)
        data = client.get(f"/api/tournaments/{tid}").get_json()
        assert data["standings"][0]["rank"] == 1

    def test_get_standings_entry_fields(self, client):
        """PARE-46: each standing entry has rank, name, best_score, submitted_at."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        data = client.get(f"/api/tournaments/{tid}").get_json()
        entry = data["standings"][0]
        assert set(entry.keys()) == {"rank", "name", "best_score", "submitted_at"}


# ===========================================================================
# PARE-47 — POST /api/tournaments/<id>/complete
# ===========================================================================

class TestCompleteTournament:
    def _setup_completable(self, client):
        """Create a tournament whose ends_at is in the past."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        # Backdate starts_at and ends_at to the past
        with db.get_db() as conn:
            conn.execute(
                "UPDATE tournaments SET status='active', starts_at=?, ends_at=? WHERE id=?",
                (past_ts(7200), past_ts(3600), tid)
            )
            conn.commit()
        return tid

    def test_complete_returns_200(self, client):
        """PARE-47: completing a past tournament returns 200."""
        tid = self._setup_completable(client)
        resp = client.post(f"/api/tournaments/{tid}/complete")
        assert resp.status_code == 200

    def test_complete_status_is_completed(self, client):
        """PARE-47: status becomes 'completed' after completing."""
        tid = self._setup_completable(client)
        data = client.post(f"/api/tournaments/{tid}/complete").get_json()
        assert data["status"] == "completed"

    def test_complete_response_includes_standings(self, client):
        """PARE-47: response includes standings."""
        tid = self._setup_completable(client)
        data = client.post(f"/api/tournaments/{tid}/complete").get_json()
        assert "standings" in data

    def test_complete_not_found_returns_404(self, client):
        """PARE-47: non-existent tournament → 404."""
        resp = client.post("/api/tournaments/9999/complete")
        assert resp.status_code == 404

    def test_complete_before_ends_at_returns_422(self, client):
        """PARE-47: completing before ends_at → 422."""
        t = create_tournament(client).get_json()
        resp = client.post(f"/api/tournaments/{t['id']}/complete")
        assert resp.status_code == 422

    def test_complete_already_completed_returns_422(self, client):
        """PARE-47: completing an already completed tournament → 422."""
        tid = self._setup_completable(client)
        client.post(f"/api/tournaments/{tid}/complete")
        resp = client.post(f"/api/tournaments/{tid}/complete")
        assert resp.status_code == 422

    def test_complete_persists_status(self, client):
        """PARE-47: completed status persists on subsequent GET."""
        tid = self._setup_completable(client)
        client.post(f"/api/tournaments/{tid}/complete")
        data = client.get(f"/api/tournaments/{tid}").get_json()
        assert data["status"] == "completed"


# ===========================================================================
# PARE-48 — Integration: full tournament lifecycle
# ===========================================================================

class TestTournamentLifecycle:
    def test_full_lifecycle(self, client):
        """PARE-48: full lifecycle open→active→complete with standings."""
        import database as db

        # 1. Create tournament
        t = create_tournament(client, name="Season 1").get_json()
        tid = t["id"]
        assert t["status"] == "open"

        # 2. Force active (simulate time passing)
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()

        # 3. Players join
        join_tournament(client, tid, "Alice")
        join_tournament(client, tid, "Bob")
        join_tournament(client, tid, "Carol")

        # 4. Players submit scores
        submit_score(client, tid, "Alice", 1500)
        submit_score(client, tid, "Bob", 1200)
        submit_score(client, tid, "Alice", 900)   # lower — should not update

        # 5. Check standings mid-game
        detail = client.get(f"/api/tournaments/{tid}").get_json()
        standings = detail["standings"]
        assert standings[0]["name"] == "Alice"
        assert standings[0]["best_score"] == 1500
        assert standings[1]["name"] == "Bob"
        assert standings[1]["best_score"] == 1200
        # Carol has no score — should be last
        carol = next(s for s in standings if s["name"] == "Carol")
        assert carol["best_score"] is None

        # 6. Complete tournament
        with db.get_db() as conn:
            conn.execute(
                "UPDATE tournaments SET ends_at=? WHERE id=?",
                (past_ts(60), tid)
            )
            conn.commit()
        final = client.post(f"/api/tournaments/{tid}/complete").get_json()
        assert final["status"] == "completed"
        assert final["standings"][0]["name"] == "Alice"

    def test_list_filter_by_status(self, client):
        """PARE-48: list endpoint filters work across multiple tournaments."""
        create_tournament(client, name="Cup A")
        create_tournament(client, name="Cup B")
        open_list = client.get("/api/tournaments?status=open").get_json()
        assert len(open_list) == 2
        completed_list = client.get("/api/tournaments?status=completed").get_json()
        assert completed_list == []

    def test_join_active_tournament(self, client):
        """PARE-48: can join a tournament after it becomes active."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        resp = join_tournament(client, tid, "Late Joiner")
        assert resp.status_code == 201

    def test_dynamic_status_open_to_active(self, client):
        """PARE-48: tournament transitions open→active on read when starts_at has passed."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        # Manually set starts_at to the past while keeping status='open'
        with db.get_db() as conn:
            conn.execute(
                "UPDATE tournaments SET starts_at=? WHERE id=?",
                (past_ts(60), tid)
            )
            conn.commit()
        # Now reading should trigger the transition
        data = client.get(f"/api/tournaments/{tid}").get_json()
        assert data["status"] == "active"

    def test_score_does_not_pollute_global_scores(self, client):
        """PARE-48: tournament scores don't appear in /api/scores."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        with db.get_db() as conn:
            conn.execute("UPDATE tournaments SET status='active' WHERE id=?", (tid,))
            conn.commit()
        join_tournament(client, tid, "Alice")
        submit_score(client, tid, "Alice", 9999)
        scores = client.get("/api/scores").get_json()
        assert all(s.get("score") != 9999 for s in scores)


# ===========================================================================
# PARE-51 — GET /api/scoreboard
# ===========================================================================

class TestGetApiScoreboard:
    def test_returns_200(self, client):
        """PARE-51: GET /api/scoreboard returns 200."""
        resp = client.get("/api/scoreboard")
        assert resp.status_code == 200

    def test_scores_field_present(self, client):
        """PARE-51: response has 'scores' key."""
        data = client.get("/api/scoreboard").get_json()
        assert "scores" in data

    def test_active_tournament_null_when_none(self, client):
        """PARE-51: active_tournament is null when no active tournament exists."""
        data = client.get("/api/scoreboard").get_json()
        assert data["active_tournament"] is None

    def test_scores_top_10(self, client):
        """PARE-51: scores array has at most 10 entries ordered score DESC."""
        # Insert 15 scores
        for i in range(15):
            post_score(client, f"Player{i}", (i + 1) * 100)
        data = client.get("/api/scoreboard").get_json()
        scores = data["scores"]
        assert len(scores) <= 10
        # Verify ordering
        for i in range(len(scores) - 1):
            assert scores[i]["score"] >= scores[i + 1]["score"]

    def test_active_tournament_populated(self, client):
        """PARE-51: when an active tournament exists, active_tournament has id, name, status, standings."""
        import database as db
        t = create_tournament(client).get_json()
        tid = t["id"]
        # Force it active
        with db.get_db() as conn:
            conn.execute(
                "UPDATE tournaments SET status='active', starts_at=? WHERE id=?",
                (past_ts(60), tid),
            )
            conn.commit()
        join_tournament(client, tid, "Alice")
        data = client.get("/api/scoreboard").get_json()
        at = data["active_tournament"]
        assert at is not None
        assert "id" in at
        assert "name" in at
        assert "status" in at
        assert "standings" in at
        assert at["status"] == "active"


# ===========================================================================
# PARE-51 — GET /scoreboard (HTML)
# ===========================================================================

class TestGetScoreboard:
    def test_returns_200(self, client):
        """PARE-51: GET /scoreboard returns 200."""
        resp = client.get("/scoreboard")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        """PARE-51: content-type is text/html."""
        resp = client.get("/scoreboard")
        assert "text/html" in resp.content_type

    def test_contains_scores(self, client):
        """PARE-51: response body contains score data when scores exist."""
        post_score(client, "TestPlayer", 4200)
        resp = client.get("/scoreboard")
        body = resp.data.decode("utf-8")
        assert "TestPlayer" in body
        assert "4200" in body


# ===========================================================================
# PARE-52 — GET /api/player/<name> and GET /player/<name>
# ===========================================================================

class TestGetPlayerHistory:
    """Tests for GET /api/player/<name> — individual player history JSON."""

    def test_existing_player_returns_200(self, client):
        """PARE-52: known player returns 200."""
        post_score(client, "PixelKnight", 500)
        resp = client.get("/api/player/PixelKnight")
        assert resp.status_code == 200

    def test_nonexistent_player_returns_404(self, client):
        """PARE-52: /api/player/NonExistent returns 404."""
        resp = client.get("/api/player/NonExistent")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_response_shape(self, client):
        """PARE-52: response has name, scores, total_games, best_score, average_score."""
        post_score(client, "PixelKnight", 300)
        data = client.get("/api/player/PixelKnight").get_json()
        assert set(data.keys()) == {"name", "scores", "total_games", "best_score", "average_score"}

    def test_name_matches(self, client):
        """PARE-52: returned name matches the queried player."""
        post_score(client, "PixelKnight", 300)
        data = client.get("/api/player/PixelKnight").get_json()
        assert data["name"] == "PixelKnight"

    def test_scores_is_list(self, client):
        """PARE-52: scores field is a list."""
        post_score(client, "PixelKnight", 300)
        data = client.get("/api/player/PixelKnight").get_json()
        assert isinstance(data["scores"], list)

    def test_scores_entry_fields(self, client):
        """PARE-52: each score entry has score and created_at."""
        post_score(client, "PixelKnight", 300)
        data = client.get("/api/player/PixelKnight").get_json()
        assert len(data["scores"]) == 1
        assert set(data["scores"][0].keys()) == {"score", "created_at"}

    def test_all_scores_returned(self, client):
        """PARE-52: all scores for the player are returned (not just best)."""
        for s in [100, 200, 300]:
            post_score(client, "PixelKnight", s)
        data = client.get("/api/player/PixelKnight").get_json()
        assert data["total_games"] == 3
        assert len(data["scores"]) == 3

    def test_best_score_correct(self, client):
        """PARE-52: best_score is the highest score."""
        for s in [100, 500, 300]:
            post_score(client, "PixelKnight", s)
        data = client.get("/api/player/PixelKnight").get_json()
        assert data["best_score"] == 500

    def test_average_score_correct(self, client):
        """PARE-52: average_score is the mean of all scores."""
        for s in [100, 200, 300]:
            post_score(client, "PixelKnight", s)
        data = client.get("/api/player/PixelKnight").get_json()
        assert abs(data["average_score"] - 200.0) < 0.01

    def test_total_games_correct(self, client):
        """PARE-52: total_games equals number of score entries."""
        for s in [100, 200]:
            post_score(client, "PixelKnight", s)
        data = client.get("/api/player/PixelKnight").get_json()
        assert data["total_games"] == 2

    def test_only_own_scores_returned(self, client):
        """PARE-52: scores from other players do not appear."""
        post_score(client, "PixelKnight", 300)
        post_score(client, "OtherPlayer", 999)
        data = client.get("/api/player/PixelKnight").get_json()
        assert data["total_games"] == 1
        assert data["best_score"] == 300

    def test_returns_json_content_type(self, client):
        """PARE-52: Content-Type is application/json."""
        post_score(client, "PixelKnight", 100)
        resp = client.get("/api/player/PixelKnight")
        assert "application/json" in resp.content_type


class TestPlayerPage:
    """Tests for GET /player/<name> — HTML player history page."""

    def test_existing_player_returns_200(self, client):
        """PARE-52: /player/PixelKnight returns 200 when player exists."""
        post_score(client, "PixelKnight", 500)
        resp = client.get("/player/PixelKnight")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        """PARE-52: content-type is text/html."""
        post_score(client, "PixelKnight", 500)
        resp = client.get("/player/PixelKnight")
        assert "text/html" in resp.content_type

    def test_contains_player_name_heading(self, client):
        """PARE-52: page contains player name heading."""
        post_score(client, "PixelKnight", 500)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        assert "PixelKnight" in body

    def test_contains_score_history(self, client):
        """PARE-52: page contains score history entries."""
        post_score(client, "PixelKnight", 750)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        assert "750" in body

    def test_contains_svg_chart(self, client):
        """PARE-52: page contains an SVG element for the bar chart."""
        post_score(client, "PixelKnight", 500)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        assert "<svg" in body

    def test_svg_has_bars(self, client):
        """PARE-52: SVG contains one rect per score entry."""
        for s in [100, 200, 300]:
            post_score(client, "PixelKnight", s)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        # 3 bars means 3 <rect elements
        assert body.count("<rect") == 3

    def test_contains_stats_summary(self, client):
        """PARE-52: page contains total games, best score, average score."""
        for s in [100, 200, 300]:
            post_score(client, "PixelKnight", s)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        assert "Total Games" in body or "total" in body.lower()
        assert "Best Score" in body or "best" in body.lower()
        assert "Average" in body or "average" in body.lower()

    def test_nonexistent_player_still_200(self, client):
        """PARE-52: /player/NonExistent returns 200 with not-found message."""
        resp = client.get("/player/NonExistent")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "NonExistent" in body

    def test_back_link_present(self, client):
        """PARE-52: page includes a back link to /scoreboard."""
        post_score(client, "PixelKnight", 500)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        assert "/scoreboard" in body

    def test_multiple_scores_all_visible_in_table(self, client):
        """PARE-52: all individual score values appear in the score history table."""
        scores = [1000, 2000, 3000, 4000]
        for s in scores:
            post_score(client, "PixelKnight", s)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        for s in scores:
            assert str(s) in body

    def test_not_found_page_no_svg_chart(self, client):
        """PARE-52: not-found page does not render an SVG chart."""
        resp = client.get("/player/GhostPlayer")
        body = resp.data.decode("utf-8")
        assert "<svg" not in body

    def test_page_title_contains_player_name(self, client):
        """PARE-52: <title> element includes the player name."""
        post_score(client, "PixelKnight", 500)
        body = client.get("/player/PixelKnight").data.decode("utf-8")
        assert "<title>" in body
        title_start = body.index("<title>")
        title_end = body.index("</title>")
        assert "PixelKnight" in body[title_start:title_end]


class TestGetPlayerHistoryEdgeCases:
    """Edge-case tests for PARE-52 /api/player/<name>."""

    def test_scores_ordered_by_created_at_desc(self, client):
        """PARE-52: scores list is sorted by created_at descending.

        Note: scores inserted within the same second share the same
        CURRENT_TIMESTAMP value, so tie-breaking order is not tested here.
        We verify the created_at values are non-increasing (i.e. the sort
        direction is correct when timestamps differ).
        """
        for s in [100, 200, 300]:
            post_score(client, "PixelKnight", s)
        data = client.get("/api/player/PixelKnight").get_json()
        timestamps = [e["created_at"] for e in data["scores"]]
        # created_at values must be in non-increasing (DESC) order
        assert timestamps == sorted(timestamps, reverse=True)

    def test_single_score_stats(self, client):
        """PARE-52: single score means best == average == that score, total_games == 1."""
        post_score(client, "PixelKnight", 7500)
        data = client.get("/api/player/PixelKnight").get_json()
        assert data["total_games"] == 1
        assert data["best_score"] == 7500
        assert abs(data["average_score"] - 7500.0) < 0.01

    def test_average_score_rounded(self, client):
        """PARE-52: average_score is rounded to 2 decimal places."""
        for s in [1, 2, 3]:  # avg = 2.0, but tests rounding contract
            post_score(client, "PixelKnight", s)
        data = client.get("/api/player/PixelKnight").get_json()
        # Verify it's not a raw float with many decimals
        avg_str = str(data["average_score"])
        if "." in avg_str:
            assert len(avg_str.split(".")[1]) <= 2

    def test_case_sensitive_player_name(self, client):
        """PARE-52: player name lookup is case-sensitive."""
        post_score(client, "PixelKnight", 500)
        resp = client.get("/api/player/pixelknight")
        assert resp.status_code == 404

    def test_multiple_players_isolated(self, client):
        """PARE-52: history for PlayerA doesn't include PlayerB's scores."""
        for s in [100, 200]:
            post_score(client, "Alice", s)
        for s in [900, 800]:
            post_score(client, "Bob", s)
        alice_data = client.get("/api/player/Alice").get_json()
        bob_data = client.get("/api/player/Bob").get_json()
        assert alice_data["best_score"] == 200
        assert bob_data["best_score"] == 900
        assert alice_data["total_games"] == 2
        assert bob_data["total_games"] == 2

    def test_tournaments_route_exists(self, client):
        """Route re-added in 34df758: GET /tournaments returns 200."""
        resp = client.get("/tournaments")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PARE-53 — Game history page
# ---------------------------------------------------------------------------

class TestApiHistory:
    """Tests for GET /api/history."""

    def test_returns_200_empty(self, client):
        """PARE-53: /api/history returns 200 with empty list when no scores."""
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_recent_scores_default_limit(self, client):
        """PARE-53: /api/history returns up to 20 most recent scores by default."""
        for i in range(25):
            post_score(client, f"Player{i}", (i + 1) * 10)
        data = client.get("/api/history").get_json()
        assert len(data) == 20

    def test_custom_limit(self, client):
        """PARE-53: /api/history?limit=5 returns exactly 5 scores."""
        for i in range(10):
            post_score(client, "Alice", (i + 1) * 100)
        data = client.get("/api/history?limit=5").get_json()
        assert len(data) == 5

    def test_limit_capped_at_100(self, client):
        """PARE-53: limit is capped at 100 even if a larger value is requested."""
        for i in range(110):
            post_score(client, "Bob", i + 1)
        data = client.get("/api/history?limit=200").get_json()
        assert len(data) == 100

    def test_ordered_by_created_at_desc(self, client):
        """PARE-53: results are ordered by created_at descending (most recent first)."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        data = client.get("/api/history").get_json()
        timestamps = [e["created_at"] for e in data]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_entry_has_required_fields(self, client):
        """PARE-53: each entry includes name, score, created_at, and time_ago."""
        post_score(client, "Alice", 500)
        data = client.get("/api/history").get_json()
        assert len(data) == 1
        entry = data[0]
        assert "name" in entry
        assert "score" in entry
        assert "created_at" in entry
        assert "time_ago" in entry

    def test_time_ago_is_string(self, client):
        """PARE-53: time_ago field is a non-empty string."""
        post_score(client, "Alice", 500)
        data = client.get("/api/history").get_json()
        assert isinstance(data[0]["time_ago"], str)
        assert len(data[0]["time_ago"]) > 0

    def test_invalid_limit_returns_400(self, client):
        """PARE-53: non-integer limit returns 400."""
        resp = client.get("/api/history?limit=abc")
        assert resp.status_code == 400

    def test_zero_limit_returns_empty(self, client):
        """PARE-53: limit=0 returns an empty list."""
        post_score(client, "Alice", 500)
        data = client.get("/api/history?limit=0").get_json()
        assert data == []


class TestHistoryPage:
    """Tests for GET /history HTML page."""

    def test_returns_200(self, client):
        """PARE-53: /history returns 200."""
        resp = client.get("/history")
        assert resp.status_code == 200

    def test_shows_player_name(self, client):
        """PARE-53: /history renders the submitted player name."""
        post_score(client, "HistoryPlayer", 999)
        body = client.get("/history").data.decode("utf-8")
        assert "HistoryPlayer" in body

    def test_shows_score(self, client):
        """PARE-53: /history renders the submitted score."""
        post_score(client, "Alice", 1234)
        body = client.get("/history").data.decode("utf-8")
        assert "1234" in body

    def test_shows_relative_time(self, client):
        """PARE-53: /history renders a relative time string in each row."""
        post_score(client, "Alice", 500)
        body = client.get("/history").data.decode("utf-8")
        assert "ago" in body

    def test_shows_rank_column(self, client):
        """PARE-53: /history table includes rank numbers."""
        post_score(client, "Alice", 500)
        body = client.get("/history").data.decode("utf-8")
        assert "1" in body

    def test_navigation_link_to_history_on_index(self, client):
        """PARE-53: index page contains a link to /history."""
        body = client.get("/").data.decode("utf-8")
        assert "/history" in body

    def test_empty_state_message(self, client):
        """PARE-53: /history shows an empty state when no scores exist."""
        resp = client.get("/history")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "No scores yet" in body or "<table" in body

    def test_max_20_rows_shown(self, client):
        """PARE-53: /history shows at most 20 rows."""
        for i in range(25):
            post_score(client, f"P{i}", (i + 1) * 10)
        body = client.get("/history").data.decode("utf-8")
        # Count <tr> rows in tbody by counting player name occurrences;
        # each row has exactly one name cell — ensure only 20 are shown.
        row_count = body.count("ago")
        assert row_count <= 20


# ---------------------------------------------------------------------------
# PARE-54 — About API and page tests
# ---------------------------------------------------------------------------

class TestAboutAPI:
    """Tests for GET /api/about."""

    def test_returns_200(self, client):
        """PARE-54: /api/about returns 200."""
        resp = client.get("/api/about")
        assert resp.status_code == 200

    def test_json_shape(self, client):
        """PARE-54: /api/about returns correct JSON keys."""
        data = client.get("/api/about").get_json()
        assert "name" in data
        assert "version" in data
        assert "total_players" in data
        assert "total_scores" in data
        assert "total_tournaments" in data

    def test_app_name_and_version(self, client):
        """PARE-54: /api/about returns correct name and version."""
        data = client.get("/api/about").get_json()
        assert data["name"] == "Game Score Tracker"
        assert data["version"] == "1.0.0"

    def test_counts_are_zero_when_empty(self, client):
        """PARE-54: counts are 0 when no data exists."""
        data = client.get("/api/about").get_json()
        assert data["total_players"] == 0
        assert data["total_scores"] == 0
        assert data["total_tournaments"] == 0

    def test_total_scores_count(self, client):
        """PARE-54: total_scores reflects submitted scores."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        post_score(client, "Bob", 150)
        data = client.get("/api/about").get_json()
        assert data["total_scores"] == 3

    def test_total_players_unique(self, client):
        """PARE-54: total_players counts distinct names."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        post_score(client, "Bob", 150)
        data = client.get("/api/about").get_json()
        assert data["total_players"] == 2

    def test_total_tournaments_count(self, client):
        """PARE-54: total_tournaments counts created tournaments."""
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        ends = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        client.post("/api/tournaments", json={"name": "T1", "starts_at": future, "ends_at": ends})
        data = client.get("/api/about").get_json()
        assert data["total_tournaments"] == 1


class TestAboutPage:
    """Tests for GET /about HTML page."""

    def test_returns_200(self, client):
        """PARE-54: /about returns 200."""
        resp = client.get("/about")
        assert resp.status_code == 200

    def test_shows_app_name(self, client):
        """PARE-54: /about renders the app name."""
        body = client.get("/about").data.decode("utf-8")
        assert "Game Score Tracker" in body

    def test_shows_version(self, client):
        """PARE-54: /about renders the version."""
        body = client.get("/about").data.decode("utf-8")
        assert "1.0.0" in body

    def test_shows_player_count(self, client):
        """PARE-54: /about renders the total unique players count."""
        post_score(client, "Alice", 100)
        post_score(client, "Bob", 200)
        body = client.get("/about").data.decode("utf-8")
        assert "2" in body

    def test_shows_score_count(self, client):
        """PARE-54: /about renders total scores submitted."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        body = client.get("/about").data.decode("utf-8")
        assert "2" in body

    def test_shows_tournament_count(self, client):
        """PARE-54: /about renders total tournaments created."""
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        ends = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        client.post("/api/tournaments", json={"name": "T1", "starts_at": future, "ends_at": ends})
        body = client.get("/about").data.decode("utf-8")
        assert "1" in body

    def test_dark_theme_link(self, client):
        """PARE-54: /about includes the shared CSS stylesheet."""
        body = client.get("/about").data.decode("utf-8")
        assert "style.css" in body


# ---------------------------------------------------------------------------
# PARE-54 additional edge case tests (added by Tester)
# ---------------------------------------------------------------------------

class TestAboutAPIEdgeCases:
    """Extra edge cases for /api/about not covered by the coder's tests."""

    def test_content_type_is_json(self, client):
        """PARE-54: /api/about must return Content-Type application/json."""
        resp = client.get("/api/about")
        assert "application/json" in resp.content_type

    def test_counts_update_after_more_scores(self, client):
        """PARE-54: counts reflect all data, not a cached snapshot."""
        post_score(client, "Alice", 100)
        data1 = client.get("/api/about").get_json()
        assert data1["total_scores"] == 1
        post_score(client, "Bob", 200)
        data2 = client.get("/api/about").get_json()
        assert data2["total_scores"] == 2
        assert data2["total_players"] == 2

    def test_total_players_not_inflated_by_duplicate_names(self, client):
        """PARE-54: same player submitting many scores counts as 1 unique player."""
        for score in [10, 20, 30, 40, 50]:
            post_score(client, "SamePlayer", score)
        data = client.get("/api/about").get_json()
        assert data["total_players"] == 1
        assert data["total_scores"] == 5

    def test_version_is_string(self, client):
        """PARE-54: version field must be a string, not a number."""
        data = client.get("/api/about").get_json()
        assert isinstance(data["version"], str)

    def test_counts_are_integers(self, client):
        """PARE-54: count fields must be integers."""
        data = client.get("/api/about").get_json()
        assert isinstance(data["total_players"], int)
        assert isinstance(data["total_scores"], int)
        assert isinstance(data["total_tournaments"], int)

    def test_multiple_tournaments_counted(self, client):
        """PARE-54: total_tournaments counts each tournament created."""
        from datetime import datetime, timezone, timedelta
        for i in range(3):
            future = (datetime.now(timezone.utc) + timedelta(hours=i + 1)).isoformat()
            ends = (datetime.now(timezone.utc) + timedelta(hours=i + 2)).isoformat()
            client.post("/api/tournaments", json={
                "name": f"Tournament {i}", "starts_at": future, "ends_at": ends
            })
        data = client.get("/api/about").get_json()
        assert data["total_tournaments"] == 3

    def test_no_extra_unexpected_keys(self, client):
        """PARE-54: API response contains exactly the expected keys, nothing extra."""
        data = client.get("/api/about").get_json()
        expected_keys = {"name", "version", "total_players", "total_scores", "total_tournaments"}
        assert set(data.keys()) == expected_keys


class TestAboutPageEdgeCases:
    """Extra edge cases for GET /about HTML page."""

    def test_has_back_link(self, client):
        """PARE-54: /about page must include a navigation link back to home."""
        body = client.get("/about").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_title_tag_present(self, client):
        """PARE-54: /about page must have a <title> tag."""
        body = client.get("/about").data.decode("utf-8")
        assert "<title>" in body.lower()

    def test_shows_zero_counts_when_empty(self, client):
        """PARE-54: /about page renders 0 stats when DB is empty."""
        body = client.get("/about").data.decode("utf-8")
        assert "0" in body

    def test_labels_present(self, client):
        """PARE-54: /about page must label each stat clearly."""
        body = client.get("/about").data.decode("utf-8")
        assert "Player" in body or "player" in body
        assert "Score" in body or "score" in body
        assert "Tournament" in body or "tournament" in body

    def test_method_not_allowed_post(self, client):
        """PARE-54: POST /about is not a valid endpoint — expect 405."""
        resp = client.post("/about", json={})
        assert resp.status_code == 405

    def test_method_not_allowed_api_post(self, client):
        """PARE-54: POST /api/about is not a valid endpoint — expect 405."""
        resp = client.post("/api/about", json={})
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# PARE-61: Badge system
# ---------------------------------------------------------------------------

class TestApiBadges:
    """Tests for GET /api/badges [PARE-61]."""

    def test_empty_db_returns_empty_list(self, client):
        """PARE-61: No scores -> no badges."""
        data = client.get("/api/badges").get_json()
        assert data == []

    def test_returns_200(self, client):
        """PARE-61: /api/badges returns HTTP 200."""
        resp = client.get("/api/badges")
        assert resp.status_code == 200

    def test_gold_badge_assigned(self, client):
        """PARE-61: Player with best_score >= 8000 gets gold."""
        client.post("/api/scores", json={"name": "Alice", "score": 8000})
        data = client.get("/api/badges").get_json()
        alice = next((b for b in data if b["player"] == "Alice"), None)
        assert alice is not None
        assert alice["badge"] == "gold"
        assert alice["best_score"] == 8000

    def test_silver_badge_assigned(self, client):
        """PARE-61: Player with best_score in 5000-7999 gets silver."""
        client.post("/api/scores", json={"name": "Bob", "score": 5000})
        data = client.get("/api/badges").get_json()
        bob = next((b for b in data if b["player"] == "Bob"), None)
        assert bob is not None
        assert bob["badge"] == "silver"
        assert bob["best_score"] == 5000

    def test_bronze_badge_assigned(self, client):
        """PARE-61: Player with best_score in 2000-4999 gets bronze."""
        client.post("/api/scores", json={"name": "Carol", "score": 2000})
        data = client.get("/api/badges").get_json()
        carol = next((b for b in data if b["player"] == "Carol"), None)
        assert carol is not None
        assert carol["badge"] == "bronze"
        assert carol["best_score"] == 2000

    def test_below_threshold_excluded(self, client):
        """PARE-61: Player with best_score < 2000 does not appear."""
        client.post("/api/scores", json={"name": "Dave", "score": 1999})
        data = client.get("/api/badges").get_json()
        dave = next((b for b in data if b["player"] == "Dave"), None)
        assert dave is None

    def test_uses_best_score(self, client):
        """PARE-61: Badge is based on MAX(score) for each player."""
        client.post("/api/scores", json={"name": "Eve", "score": 1000})
        client.post("/api/scores", json={"name": "Eve", "score": 9000})
        data = client.get("/api/badges").get_json()
        eve = next((b for b in data if b["player"] == "Eve"), None)
        assert eve is not None
        assert eve["badge"] == "gold"
        assert eve["best_score"] == 9000

    def test_response_keys(self, client):
        """PARE-61: Each badge entry has exactly player, badge, best_score keys."""
        client.post("/api/scores", json={"name": "Frank", "score": 3000})
        data = client.get("/api/badges").get_json()
        assert len(data) == 1
        assert set(data[0].keys()) == {"player", "badge", "best_score"}

    def test_multiple_badges(self, client):
        """PARE-61: Multiple players each get the correct badge."""
        client.post("/api/scores", json={"name": "Gold1", "score": 8500})
        client.post("/api/scores", json={"name": "Silver1", "score": 6000})
        client.post("/api/scores", json={"name": "Bronze1", "score": 3000})
        client.post("/api/scores", json={"name": "NoBadge", "score": 500})
        data = client.get("/api/badges").get_json()
        by_player = {b["player"]: b for b in data}
        assert by_player["Gold1"]["badge"] == "gold"
        assert by_player["Silver1"]["badge"] == "silver"
        assert by_player["Bronze1"]["badge"] == "bronze"
        assert "NoBadge" not in by_player

    def test_silver_upper_boundary(self, client):
        """PARE-61: Score of 7999 gets silver (not gold)."""
        client.post("/api/scores", json={"name": "Upper", "score": 7999})
        data = client.get("/api/badges").get_json()
        entry = next((b for b in data if b["player"] == "Upper"), None)
        assert entry is not None
        assert entry["badge"] == "silver"

    def test_bronze_upper_boundary(self, client):
        """PARE-61: Score of 4999 gets bronze (not silver)."""
        client.post("/api/scores", json={"name": "BUpper", "score": 4999})
        data = client.get("/api/badges").get_json()
        entry = next((b for b in data if b["player"] == "BUpper"), None)
        assert entry is not None
        assert entry["badge"] == "bronze"


class TestBadgesPage:
    """Tests for GET /badges HTML page [PARE-61]."""

    def test_returns_200(self, client):
        """PARE-61: /badges returns HTTP 200."""
        resp = client.get("/badges")
        assert resp.status_code == 200

    def test_has_title(self, client):
        """PARE-61: /badges page has a <title> tag."""
        body = client.get("/badges").data.decode("utf-8")
        assert "<title>" in body.lower()

    def test_has_back_link(self, client):
        """PARE-61: /badges page has a link back to home."""
        body = client.get("/badges").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_shows_badge_summary(self, client):
        """PARE-61: /badges page shows count summary with Gold/Silver/Bronze labels."""
        body = client.get("/badges").data.decode("utf-8")
        assert "Gold" in body
        assert "Silver" in body
        assert "Bronze" in body

    def test_shows_player_in_grid(self, client):
        """PARE-61: /badges page shows a badged player in the grid."""
        client.post("/api/scores", json={"name": "GridPlayer", "score": 8000})
        body = client.get("/badges").data.decode("utf-8")
        assert "GridPlayer" in body

    def test_player_below_threshold_not_shown(self, client):
        """PARE-61: Players below 2000 do not appear on /badges page."""
        client.post("/api/scores", json={"name": "NoBadgePlayer", "score": 100})
        body = client.get("/badges").data.decode("utf-8")
        assert "NoBadgePlayer" not in body

    def test_gold_color_class_present(self, client):
        """PARE-61: Gold badge entries use a gold CSS class or color indicator."""
        client.post("/api/scores", json={"name": "GoldGuy", "score": 9000})
        body = client.get("/badges").data.decode("utf-8")
        assert "gold" in body

    def test_silver_color_class_present(self, client):
        """PARE-61: Silver badge entries use a silver CSS class or color indicator."""
        client.post("/api/scores", json={"name": "SilverGuy", "score": 6000})
        body = client.get("/badges").data.decode("utf-8")
        assert "silver" in body

    def test_bronze_color_class_present(self, client):
        """PARE-61: Bronze badge entries use a bronze CSS class or color indicator."""
        client.post("/api/scores", json={"name": "BronzeGuy", "score": 3000})
        body = client.get("/badges").data.decode("utf-8")
        assert "bronze" in body

    def test_empty_state_message(self, client):
        """PARE-61: /badges shows a message when no badges awarded."""
        body = client.get("/badges").data.decode("utf-8")
        assert "No badges" in body or "no badges" in body or "0" in body

    def test_method_not_allowed_post(self, client):
        """PARE-61: POST /badges is not a valid endpoint — expect 405."""
        resp = client.post("/badges", json={})
        assert resp.status_code == 405

    def test_method_not_allowed_api_post(self, client):
        """PARE-61: POST /api/badges is not a valid endpoint — expect 405."""
        resp = client.post("/api/badges", json={})
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# PARE-67 — Player achievements system
# ---------------------------------------------------------------------------

class TestApiAchievements:
    """Tests for GET /api/achievements [PARE-67]."""

    def test_returns_200(self, client):
        """PARE-67: /api/achievements returns HTTP 200."""
        resp = client.get("/api/achievements")
        assert resp.status_code == 200

    def test_empty_db_returns_empty_list(self, client):
        """PARE-67: No scores -> empty array."""
        data = client.get("/api/achievements").get_json()
        assert data == []

    def test_response_entry_fields(self, client):
        """PARE-67: each entry has player, achievements, total_scores."""
        post_score(client, "Alice", 100)
        data = client.get("/api/achievements").get_json()
        assert len(data) == 1
        assert set(data[0].keys()) == {"player", "achievements", "total_scores"}

    def test_first_blood_milestone(self, client):
        """PARE-67: 1+ scores earns First Blood."""
        post_score(client, "Alice", 100)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert "First Blood" in alice["achievements"]

    def test_veteran_milestone(self, client):
        """PARE-67: 10+ scores earns Veteran."""
        for i in range(10):
            post_score(client, "Alice", 100)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert "Veteran" in alice["achievements"]

    def test_veteran_requires_10(self, client):
        """PARE-67: 9 scores do NOT earn Veteran."""
        for i in range(9):
            post_score(client, "Alice", 100)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert "Veteran" not in alice["achievements"]

    def test_champion_milestone(self, client):
        """PARE-67: score >= 9000 earns Champion."""
        post_score(client, "Alice", 9000)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert "Champion" in alice["achievements"]

    def test_champion_requires_9000(self, client):
        """PARE-67: score of 8999 does NOT earn Champion."""
        post_score(client, "Alice", 8999)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert "Champion" not in alice["achievements"]

    def test_all_milestones_earned(self, client):
        """PARE-67: player with 10+ scores and best >= 9000 earns all milestones."""
        for i in range(9):
            post_score(client, "Alice", 100)
        post_score(client, "Alice", 9000)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert "First Blood" in alice["achievements"]
        assert "Veteran" in alice["achievements"]
        assert "Champion" in alice["achievements"]

    def test_total_scores_correct(self, client):
        """PARE-67: total_scores reflects score count per player."""
        for _ in range(3):
            post_score(client, "Alice", 500)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert alice["total_scores"] == 3

    def test_player_no_scores_not_shown(self, client):
        """PARE-67: players with no scores don't appear."""
        data = client.get("/api/achievements").get_json()
        assert data == []

    def test_multiple_players_isolated(self, client):
        """PARE-67: each player's achievements are independent."""
        post_score(client, "Alice", 9000)
        for _ in range(10):
            post_score(client, "Bob", 100)
        data = client.get("/api/achievements").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        bob = next(d for d in data if d["player"] == "Bob")
        assert "Champion" in alice["achievements"]
        assert "Champion" not in bob["achievements"]
        assert "Veteran" in bob["achievements"]
        assert "Veteran" not in alice["achievements"]


class TestAchievementsPage:
    """Tests for GET /achievements HTML page [PARE-67]."""

    def test_returns_200(self, client):
        """PARE-67: /achievements returns HTTP 200."""
        resp = client.get("/achievements")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        """PARE-67: content-type is text/html."""
        resp = client.get("/achievements")
        assert "text/html" in resp.content_type

    def test_has_title(self, client):
        """PARE-67: /achievements page has a <title> tag."""
        body = client.get("/achievements").data.decode("utf-8")
        assert "<title>" in body.lower()

    def test_has_back_link(self, client):
        """PARE-67: /achievements page has a link back to home."""
        body = client.get("/achievements").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_shows_milestone_columns(self, client):
        """PARE-67: table headers include all milestone names."""
        body = client.get("/achievements").data.decode("utf-8")
        assert "First Blood" in body
        assert "Veteran" in body
        assert "Champion" in body

    def test_shows_player_row(self, client):
        """PARE-67: player with a score appears in the table."""
        post_score(client, "HeroPlayer", 500)
        body = client.get("/achievements").data.decode("utf-8")
        assert "HeroPlayer" in body

    def test_checkmark_for_earned_achievement(self, client):
        """PARE-67: checkmark character present for earned milestone."""
        post_score(client, "Alice", 100)
        body = client.get("/achievements").data.decode("utf-8")
        assert "\u2713" in body or "&#10003;" in body or "checkmark" in body

    def test_empty_state_no_players(self, client):
        """PARE-67: /achievements shows empty state when no players."""
        body = client.get("/achievements").data.decode("utf-8")
        assert "No players" in body or "no players" in body or "<table" not in body


# ---------------------------------------------------------------------------
# PARE-68 — Game statistics dashboard
# ---------------------------------------------------------------------------


class TestApiStats:
    """Tests for GET /api/stats [PARE-68]."""

    def test_returns_200(self, client):
        """PARE-68: /api/stats returns HTTP 200."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200

    def test_empty_db_returns_zero_fields(self, client):
        """PARE-68: Empty DB returns all 6 fields with zero/null values."""
        data = client.get("/api/stats").get_json()
        assert data["total_games"] == 0
        assert data["total_players"] == 0
        assert data["average_score"] == 0
        assert data["scores_today"] == 0

    def test_all_six_fields_present(self, client):
        """PARE-68: Response contains all 6 required fields."""
        data = client.get("/api/stats").get_json()
        assert "total_games" in data
        assert "total_players" in data
        assert "highest_score" in data
        assert "most_active_player" in data
        assert "average_score" in data
        assert "scores_today" in data

    def test_total_games_count(self, client):
        """PARE-68: total_games reflects score count."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        post_score(client, "Bob", 300)
        data = client.get("/api/stats").get_json()
        assert data["total_games"] == 3

    def test_total_players_distinct(self, client):
        """PARE-68: total_players counts distinct names."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        post_score(client, "Bob", 300)
        data = client.get("/api/stats").get_json()
        assert data["total_players"] == 2

    def test_highest_score_fields(self, client):
        """PARE-68: highest_score has name and score fields."""
        post_score(client, "Alice", 500)
        post_score(client, "Bob", 9000)
        data = client.get("/api/stats").get_json()
        assert data["highest_score"]["name"] == "Bob"
        assert data["highest_score"]["score"] == 9000

    def test_most_active_player_fields(self, client):
        """PARE-68: most_active_player has name and games_played fields."""
        post_score(client, "Alice", 100)
        post_score(client, "Alice", 200)
        post_score(client, "Bob", 300)
        data = client.get("/api/stats").get_json()
        assert data["most_active_player"]["name"] == "Alice"
        assert data["most_active_player"]["games_played"] == 2

    def test_average_score(self, client):
        """PARE-68: average_score is mean of all scores."""
        post_score(client, "Alice", 100)
        post_score(client, "Bob", 300)
        data = client.get("/api/stats").get_json()
        assert data["average_score"] == 200.0

    def test_scores_today_field_present(self, client):
        """PARE-68: scores_today is an integer."""
        data = client.get("/api/stats").get_json()
        assert isinstance(data["scores_today"], int)


class TestStatsPage:
    """Tests for GET /stats HTML page [PARE-68]."""

    def test_returns_200(self, client):
        """PARE-68: /stats returns HTTP 200."""
        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        """PARE-68: content-type is text/html."""
        resp = client.get("/stats")
        assert "text/html" in resp.content_type

    def test_has_title(self, client):
        """PARE-68: /stats page has a <title> tag."""
        body = client.get("/stats").data.decode("utf-8")
        assert "<title>" in body.lower()

    def test_has_back_link(self, client):
        """PARE-68: /stats page has a link back to home."""
        body = client.get("/stats").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_shows_six_stat_cards(self, client):
        """PARE-68: /stats page contains 6 stat cards."""
        body = client.get("/stats").data.decode("utf-8")
        assert body.count("stat-card") >= 6

    def test_shows_player_name_in_highest_score(self, client):
        """PARE-68: highest score player name appears on the page."""
        post_score(client, "TopPlayer", 9999)
        body = client.get("/stats").data.decode("utf-8")
        assert "TopPlayer" in body

    def test_shows_most_active_player_name(self, client):
        """PARE-68: most active player name appears on the page."""
        for _ in range(3):
            post_score(client, "ActivePlayer", 100)
        body = client.get("/stats").data.decode("utf-8")
        assert "ActivePlayer" in body

    def test_method_not_allowed_post(self, client):
        """PARE-68: POST /stats is not a valid endpoint — expect 405."""
        resp = client.post("/stats", json={})
        assert resp.status_code == 405

    def test_method_not_allowed_api_post(self, client):
        """PARE-68: POST /api/stats is not a valid endpoint — expect 405."""
        resp = client.post("/api/stats", json={})
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# PARE-69 — Player streak tracker
# ---------------------------------------------------------------------------

class TestApiStreaks:
    """Tests for GET /api/streaks [PARE-69]."""

    def test_returns_200(self, client):
        """PARE-69: /api/streaks returns HTTP 200."""
        resp = client.get("/api/streaks")
        assert resp.status_code == 200

    def test_empty_db_returns_empty_list(self, client):
        """PARE-69: No scores -> empty array."""
        data = client.get("/api/streaks").get_json()
        assert data == []

    def test_response_entry_fields(self, client):
        """PARE-69: each entry has player, current_streak, best_streak, last_played."""
        post_score(client, "Alice", 100)
        data = client.get("/api/streaks").get_json()
        assert len(data) == 1
        assert set(data[0].keys()) == {"player", "current_streak", "best_streak", "last_played"}

    def test_player_with_no_scores_not_shown(self, client):
        """PARE-69: players with no scores don't appear."""
        data = client.get("/api/streaks").get_json()
        assert data == []

    def test_single_score_same_day_streak(self, client):
        """PARE-69: A single score on today gives current_streak=1, best_streak=1."""
        post_score(client, "Alice", 100)
        data = client.get("/api/streaks").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert alice["current_streak"] >= 1
        assert alice["best_streak"] == 1

    def test_consecutive_days_best_streak(self, client):
        """PARE-69: Scores on consecutive days produce correct best_streak."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 200, '2026-04-11T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 300, '2026-04-12T10:00:00+00:00')"
            )
            conn.commit()
        data = client.get("/api/streaks").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert alice["best_streak"] == 3

    def test_gap_resets_streak(self, client):
        """PARE-69: A gap in days resets the streak counter."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 200, '2026-04-12T10:00:00+00:00')"
            )
            conn.commit()
        data = client.get("/api/streaks").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert alice["best_streak"] == 1

    def test_multiple_scores_same_day_counted_once(self, client):
        """PARE-69: Multiple scores on the same day count as 1 day."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 200, '2026-04-10T12:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 300, '2026-04-11T10:00:00+00:00')"
            )
            conn.commit()
        data = client.get("/api/streaks").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert alice["best_streak"] == 2

    def test_sorted_by_current_streak_desc(self, client):
        """PARE-69: Results are sorted by current_streak DESC."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Zoe', 100, '2026-04-09T10:00:00+00:00')"
            )
            conn.commit()
        post_score(client, "Alice", 200)
        data = client.get("/api/streaks").get_json()
        streaks = [d["current_streak"] for d in data]
        assert streaks == sorted(streaks, reverse=True)

    def test_multiple_players_independent(self, client):
        """PARE-69: Each player's streaks are calculated independently."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 200, '2026-04-11T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 300, '2026-04-12T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Bob', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.commit()
        data = client.get("/api/streaks").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        bob = next(d for d in data if d["player"] == "Bob")
        assert alice["best_streak"] == 3
        assert bob["best_streak"] == 1

    def test_last_played_reflects_most_recent_day(self, client):
        """PARE-69: last_played is the most recent scoring date."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 200, '2026-04-11T10:00:00+00:00')"
            )
            conn.commit()
        data = client.get("/api/streaks").get_json()
        alice = next(d for d in data if d["player"] == "Alice")
        assert alice["last_played"] == "2026-04-11"

    def test_method_not_allowed_post(self, client):
        """PARE-69: POST /api/streaks is not a valid endpoint — expect 405."""
        resp = client.post("/api/streaks", json={})
        assert resp.status_code == 405


class TestStreaksPage:
    """Tests for GET /streaks HTML page [PARE-69]."""

    def test_returns_200(self, client):
        """PARE-69: /streaks returns HTTP 200."""
        resp = client.get("/streaks")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        """PARE-69: content-type is text/html."""
        resp = client.get("/streaks")
        assert "text/html" in resp.content_type

    def test_has_title(self, client):
        """PARE-69: /streaks page has a <title> tag."""
        body = client.get("/streaks").data.decode("utf-8")
        assert "<title>" in body.lower()

    def test_has_back_link(self, client):
        """PARE-69: /streaks page has a link back to home."""
        body = client.get("/streaks").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_has_table_headers(self, client):
        """PARE-69: table headers include Player, Current Streak, Best Streak, Last Played."""
        post_score(client, "HeaderTest", 100)
        body = client.get("/streaks").data.decode("utf-8")
        assert "Player" in body
        assert "Current Streak" in body
        assert "Best Streak" in body
        assert "Last Played" in body

    def test_shows_player_name(self, client):
        """PARE-69: player name appears in the table."""
        post_score(client, "StreakPlayer", 100)
        body = client.get("/streaks").data.decode("utf-8")
        assert "StreakPlayer" in body

    def test_highlight_class_for_streak_ge_3(self, client):
        """PARE-69: rows with current_streak >= 3 get highlight class."""
        import database as db
        with db.get_db() as conn:
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '2026-04-10T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 200, '2026-04-11T10:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO scores (name, score, created_at) VALUES ('Alice', 300, '2026-04-12T10:00:00+00:00')"
            )
            conn.commit()
        body = client.get("/streaks").data.decode("utf-8")
        assert "highlight" in body

    def test_no_highlight_for_streak_lt_3(self, client):
        """PARE-69: rows with current_streak < 3 don't get highlight class."""
        post_score(client, "Bob", 100)
        body = client.get("/streaks").data.decode("utf-8")
        import re
        bob_row = re.search(r'<tr[^>]*>.*?Bob.*?</tr>', body, re.DOTALL)
        if bob_row:
            assert "highlight" not in bob_row.group()

    def test_empty_state_no_players(self, client):
        """PARE-69: /streaks shows empty state when no players have scores."""
        body = client.get("/streaks").data.decode("utf-8")
        assert "No streak data" in body or "<table" not in body

    def test_method_not_allowed_post(self, client):
        """PARE-69: POST /streaks is not a valid endpoint — expect 405."""
        resp = client.post("/streaks", json={})
        assert resp.status_code == 405

    def test_heatmap_section_present_with_scores(self, client):
        """T-14: heatmap section renders when there are scores."""
        post_score(client, "Alice", 100)
        body = client.get("/streaks").data.decode("utf-8")
        assert 'class="heatmap-grid"' in body

    def test_heatmap_covers_84_days(self, client):
        """T-14: heatmap renders exactly 84 cells."""
        post_score(client, "Alice", 100)
        body = client.get("/streaks").data.decode("utf-8")
        assert body.count('class="heatmap-day') == 84

    def test_heatmap_day_with_games_has_level_class(self, client):
        """T-14: a day with games gets a level-N CSS class."""
        import database as db
        from datetime import date, timedelta
        today = date.today().isoformat()
        with db.get_db() as conn:
            conn.execute(
                f"INSERT INTO scores (name, score, created_at) VALUES ('Alice', 100, '{today}T10:00:00+00:00')"
            )
            conn.commit()
        body = client.get("/streaks").data.decode("utf-8")
        assert "level-1" in body or "level-2" in body or "level-3" in body or "level-4" in body

    def test_heatmap_legend_present(self, client):
        """T-14: heatmap legend is rendered."""
        post_score(client, "Alice", 100)
        body = client.get("/streaks").data.decode("utf-8")
        assert "heatmap-legend" in body
        assert "Less" in body
        assert "More" in body

    def test_heatmap_always_84_cells_even_empty_db(self, client):
        """T-14: heatmap always renders 84 cells (zeros fill gaps)."""
        body = client.get("/streaks").data.decode("utf-8")
        assert body.count('class="heatmap-day') == 84

    def test_existing_table_headers_intact(self, client):
        """T-14: adding heatmap does not remove existing table headers."""
        post_score(client, "Alice", 100)
        body = client.get("/streaks").data.decode("utf-8")
        assert "Player" in body
        assert "Current Streak" in body
        assert "Best Streak" in body
        assert "Last Played" in body


# ---------------------------------------------------------------------------
# PARE-75 — Player profile page with stats
# ---------------------------------------------------------------------------

class TestApiPlayerProfile:
    """Tests for GET /api/player/<name>/profile [PARE-75]."""

    def test_returns_200(self, client):
        """PARE-75: known player returns 200."""
        post_score(client, "Alice", 500)
        resp = client.get("/api/player/Alice/profile")
        assert resp.status_code == 200

    def test_nonexistent_player_returns_404(self, client):
        """PARE-75: unknown player returns 404."""
        resp = client.get("/api/player/Ghost/profile")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_response_fields(self, client):
        """PARE-75: response has name, rank, total_games, avg_score, top_scores."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert set(data.keys()) == {"name", "rank", "total_games", "avg_score", "top_scores"}

    def test_name_matches(self, client):
        """PARE-75: returned name matches queried player."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert data["name"] == "Alice"

    def test_rank_single_player(self, client):
        """PARE-75: only player in DB gets rank 1."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert data["rank"] == 1

    def test_rank_ordering(self, client):
        """PARE-75: rank reflects position by best score."""
        post_score(client, "Alice", 1000)
        post_score(client, "Bob", 500)
        alice = client.get("/api/player/Alice/profile").get_json()
        bob = client.get("/api/player/Bob/profile").get_json()
        assert alice["rank"] == 1
        assert bob["rank"] == 2

    def test_total_games_correct(self, client):
        """PARE-75: total_games reflects number of scores."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        assert data["total_games"] == 3

    def test_avg_score_correct(self, client):
        """PARE-75: avg_score is mean of all scores."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        assert abs(data["avg_score"] - 200.0) < 0.01

    def test_top_scores_is_list(self, client):
        """PARE-75: top_scores is a list."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert isinstance(data["top_scores"], list)

    def test_top_scores_entry_fields(self, client):
        """PARE-75: each top_scores entry has rank, score, date."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert len(data["top_scores"]) == 1
        assert set(data["top_scores"][0].keys()) == {"rank", "score", "date"}

    def test_top_scores_capped_at_5(self, client):
        """PARE-75: top_scores has at most 5 entries."""
        for s in [100, 200, 300, 400, 500, 600, 700]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        assert len(data["top_scores"]) <= 5

    def test_top_scores_ordered_by_score_desc(self, client):
        """PARE-75: top_scores entries are ordered highest score first."""
        for s in [100, 500, 300, 200, 400]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        scores = [e["score"] for e in data["top_scores"]]
        assert scores == sorted(scores, reverse=True)

    def test_top_scores_rank_sequential(self, client):
        """PARE-75: top_scores ranks are 1, 2, 3, ..."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        ranks = [e["rank"] for e in data["top_scores"]]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_only_own_scores_counted(self, client):
        """PARE-75: stats exclude other players' scores."""
        post_score(client, "Alice", 300)
        post_score(client, "Bob", 999)
        data = client.get("/api/player/Alice/profile").get_json()
        assert data["total_games"] == 1
        assert data["top_scores"][0]["score"] == 300

    def test_returns_json_content_type(self, client):
        """PARE-75: Content-Type is application/json."""
        post_score(client, "Alice", 100)
        resp = client.get("/api/player/Alice/profile")
        assert "application/json" in resp.content_type

    def test_method_not_allowed_post(self, client):
        """PARE-75: POST /api/player/<name>/profile is not valid — expect 405."""
        post_score(client, "Alice", 100)
        resp = client.post("/api/player/Alice/profile", json={})
        assert resp.status_code == 405


class TestPlayerProfilePage:
    """Tests for GET /player/<name>/profile HTML page [PARE-75]."""

    def test_returns_200(self, client):
        """PARE-75: /player/<name>/profile returns 200 for known player."""
        post_score(client, "Alice", 500)
        resp = client.get("/player/Alice/profile")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        """PARE-75: content-type is text/html."""
        post_score(client, "Alice", 500)
        resp = client.get("/player/Alice/profile")
        assert "text/html" in resp.content_type

    def test_contains_player_name_heading(self, client):
        """PARE-75: page contains player name in heading."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "Alice" in body

    def test_has_title(self, client):
        """PARE-75: page has a <title> tag."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "<title>" in body.lower()

    def test_has_back_link(self, client):
        """PARE-75: page has a link back to home."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_shows_rank(self, client):
        """PARE-75: page displays overall rank."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "Rank" in body or "rank" in body

    def test_shows_total_games(self, client):
        """PARE-75: page displays total games."""
        for s in [100, 200]:
            post_score(client, "Alice", s)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "Total Games" in body or "total" in body.lower()

    def test_shows_avg_score(self, client):
        """PARE-75: page displays average score."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "Avg" in body or "avg" in body.lower() or "Average" in body

    def test_shows_top_scores_table(self, client):
        """PARE-75: page contains a top scores table."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "<table" in body
        assert "300" in body

    def test_top_scores_limited_to_5(self, client):
        """PARE-75: only top-5 scores appear in table rows (at most 5 data rows)."""
        for s in [100, 200, 300, 400, 500, 600, 700]:
            post_score(client, "Alice", s)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        # 100 and 200 are not top-5 out of 7 scores
        assert "100" not in body or body.count("<tr") <= 7

    def test_nonexistent_player_returns_200_not_found(self, client):
        """PARE-75: unknown player returns 200 with not-found message."""
        resp = client.get("/player/Ghost/profile")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "Ghost" in body

    def test_method_not_allowed_post(self, client):
        """PARE-75: POST /player/<name>/profile is not valid — expect 405."""
        resp = client.post("/player/Alice/profile", json={})
        assert resp.status_code == 405


class TestApiPlayerProfileEdgeCases:
    """Additional edge-case tests for PARE-75 /api/player/<name>/profile."""

    def test_rank_tied_best_score(self, client):
        """PARE-75: two players with the same best score share rank 1."""
        post_score(client, "Alice", 500)
        post_score(client, "Bob", 500)
        alice = client.get("/api/player/Alice/profile").get_json()
        bob = client.get("/api/player/Bob/profile").get_json()
        # Both should be rank 1 (no one has best_score > 500)
        assert alice["rank"] == 1
        assert bob["rank"] == 1

    def test_rank_uses_best_not_latest_score(self, client):
        """PARE-75: rank is based on max score, not the most recent one."""
        post_score(client, "Alice", 1000)
        post_score(client, "Alice", 100)  # lower — should not drop rank
        post_score(client, "Bob", 500)
        alice = client.get("/api/player/Alice/profile").get_json()
        assert alice["rank"] == 1

    def test_avg_score_is_float(self, client):
        """PARE-75: avg_score is a number (int or float)."""
        post_score(client, "Alice", 100)
        data = client.get("/api/player/Alice/profile").get_json()
        assert isinstance(data["avg_score"], (int, float))

    def test_top_scores_exactly_5_when_more_exist(self, client):
        """PARE-75: exactly 5 entries returned when player has >5 scores."""
        for s in [100, 200, 300, 400, 500, 600, 700]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        assert len(data["top_scores"]) == 5

    def test_top_scores_contains_correct_top5(self, client):
        """PARE-75: top_scores are the 5 highest scores, not the 5 most recent."""
        for s in [100, 200, 300, 400, 500, 600, 700]:
            post_score(client, "Alice", s)
        data = client.get("/api/player/Alice/profile").get_json()
        scores = [e["score"] for e in data["top_scores"]]
        # Should be 700, 600, 500, 400, 300 — not 100 or 200
        assert 700 in scores
        assert 600 in scores
        assert 100 not in scores
        assert 200 not in scores

    def test_case_sensitive_name_lookup(self, client):
        """PARE-75: name lookup is case-sensitive."""
        post_score(client, "Alice", 500)
        resp = client.get("/api/player/alice/profile")
        assert resp.status_code == 404

    def test_rank_field_is_integer(self, client):
        """PARE-75: rank is an integer, not a float or string."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert isinstance(data["rank"], int)

    def test_total_games_is_integer(self, client):
        """PARE-75: total_games is an integer."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert isinstance(data["total_games"], int)

    def test_top_scores_date_is_string(self, client):
        """PARE-75: date field in each top_scores entry is a string."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        for entry in data["top_scores"]:
            assert isinstance(entry["date"], str)

    def test_top_scores_score_is_integer(self, client):
        """PARE-75: score field in each top_scores entry is an integer."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        for entry in data["top_scores"]:
            assert isinstance(entry["score"], int)

    def test_does_not_include_other_player_scores_in_top5(self, client):
        """PARE-75: top_scores only contains the queried player's scores."""
        post_score(client, "Alice", 100)
        post_score(client, "Bob", 9999)  # Bob's high score must not appear in Alice's top5
        data = client.get("/api/player/Alice/profile").get_json()
        for entry in data["top_scores"]:
            assert entry["score"] != 9999

    def test_single_score_top_scores_has_one_entry(self, client):
        """PARE-75: single score → top_scores has exactly one entry."""
        post_score(client, "Alice", 500)
        data = client.get("/api/player/Alice/profile").get_json()
        assert len(data["top_scores"]) == 1

    def test_rank_increases_as_more_players_added(self, client):
        """PARE-75: player's rank degrades correctly as better players are added."""
        post_score(client, "Alice", 500)
        data1 = client.get("/api/player/Alice/profile").get_json()
        assert data1["rank"] == 1

        post_score(client, "Bob", 600)
        data2 = client.get("/api/player/Alice/profile").get_json()
        assert data2["rank"] == 2

        post_score(client, "Carol", 700)
        data3 = client.get("/api/player/Alice/profile").get_json()
        assert data3["rank"] == 3


class TestPlayerProfilePageEdgeCases:
    """Additional edge-case tests for PARE-75 /player/<name>/profile HTML page."""

    def test_shows_correct_rank_number(self, client):
        """PARE-75: page shows rank 1 when only one player exists."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "#1" in body or ">1<" in body or ">1 <" in body

    def test_shows_correct_total_games_count(self, client):
        """PARE-75: page renders the correct total_games count."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "3" in body

    def test_top_score_value_visible(self, client):
        """PARE-75: the highest score value appears in the page."""
        post_score(client, "Alice", 9876)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "9876" in body

    def test_not_found_page_has_no_table(self, client):
        """PARE-75: not-found page does not render the stats table."""
        body = client.get("/player/Ghost/profile").data.decode("utf-8")
        # Should not render actual stat-box div elements (CSS definitions are fine)
        # The not_found branch in the template skips the profile-container block
        assert "<table" not in body and "stat-value" not in body.split("</style>", 1)[-1]

    def test_case_sensitive_not_found(self, client):
        """PARE-75: /player/alice/profile returns 200 but shows not-found message."""
        post_score(client, "Alice", 500)
        resp = client.get("/player/alice/profile")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "alice" in body  # player name echoed back

    def test_avg_score_rounded_visible(self, client):
        """PARE-75: page renders avg_score rounded to 2 decimal places."""
        for s in [100, 200, 300]:
            post_score(client, "Alice", s)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        # avg = 200.0 — should appear on the page
        assert "200" in body

    def test_has_player_heading_class(self, client):
        """PARE-75: page uses the expected heading element for the player name."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        # The template uses class 'player-heading'
        assert "player-heading" in body

    def test_table_has_rank_score_date_headers(self, client):
        """PARE-75: top scores table contains Rank, Score, Date column headers."""
        post_score(client, "Alice", 500)
        body = client.get("/player/Alice/profile").data.decode("utf-8")
        assert "Rank" in body
        assert "Score" in body
        assert "Date" in body
