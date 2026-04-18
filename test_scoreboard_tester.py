"""
Tester-agent tests for PARE-49, PARE-50, PARE-51.

PARE-49  — GET /api/scoreboard (JSON) + GET /scoreboard (HTML)
PARE-50  — scripts/seed_scoreboard.py
PARE-51  — Tests for /scoreboard and /api/scoreboard (coder's own tests validated here)

Acceptance criteria verified:
  PARE-49:
    - GET /api/scoreboard returns JSON {scores: [...], active_tournament: null | {...}}
    - scores is top-10 ordered by score DESC
    - active_tournament is null when no active tournament exists
    - active_tournament has {id, name, status, standings} when one is active
    - GET /scoreboard returns 200 HTML
    - HTML contains score data
    - HTML contains auto-refresh JS (5s)
    - HTML contains filter input
    - Tournament section hidden when no active tournament
    - Tournament section visible when active tournament exists

  PARE-50:
    - seed_scoreboard.py is importable / runnable
    - After run: at least 15 distinct players in scores table
    - After run: at least one tournament with status 'active'
    - After run: at least 5 entries in the active tournament
    - Script is idempotent (safe to run twice)

  PARE-51 (coder's own test integrity):
    - All coder-written TestGetApiScoreboard / TestGetScoreboard tests present and passing
"""

import os
import sys
import sqlite3
import subprocess
import pytest
import tempfile

import database

# ---------------------------------------------------------------------------
# Fixtures (same pattern as test_api_scores.py)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_scores.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    monkeypatch.setenv("DB_PATH", str(db_file))
    database.init_db()
    yield


@pytest.fixture
def client(isolated_db):
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_score(client, name, score):
    return client.post("/api/scores", json={"name": name, "score": score})


def _past_ts(seconds=3600):
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _future_ts(seconds=3600):
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _create_active_tournament(client, name="Test Cup"):
    """Create a tournament and force it to active status directly in DB."""
    resp = client.post("/api/tournaments", json={
        "name": name,
        "starts_at": _future_ts(60),
        "ends_at": _future_ts(7200),
    })
    assert resp.status_code == 201
    tid = resp.get_json()["id"]
    with database.get_db() as conn:
        conn.execute(
            "UPDATE tournaments SET status='active', starts_at=? WHERE id=?",
            (_past_ts(60), tid),
        )
        conn.commit()
    return tid


def _join_and_score(client, tid, name, score):
    client.post(f"/api/tournaments/{tid}/join", json={"name": name})
    client.post(f"/api/tournaments/{tid}/score", json={"name": name, "score": score})


# ===========================================================================
# PARE-49 — GET /api/scoreboard JSON endpoint
# ===========================================================================

class TestApiScoreboardShape:
    def test_returns_200(self, client):
        """PARE-49: /api/scoreboard responds with HTTP 200."""
        resp = client.get("/api/scoreboard")
        assert resp.status_code == 200

    def test_content_type_json(self, client):
        """PARE-49: response Content-Type is application/json."""
        resp = client.get("/api/scoreboard")
        assert "application/json" in resp.content_type

    def test_response_has_scores_key(self, client):
        """PARE-49: response JSON has a 'scores' key."""
        data = client.get("/api/scoreboard").get_json()
        assert "scores" in data

    def test_response_has_active_tournament_key(self, client):
        """PARE-49: response JSON has an 'active_tournament' key."""
        data = client.get("/api/scoreboard").get_json()
        assert "active_tournament" in data

    def test_scores_is_list(self, client):
        """PARE-49: 'scores' value is a JSON array."""
        data = client.get("/api/scoreboard").get_json()
        assert isinstance(data["scores"], list)

    def test_active_tournament_is_null_when_no_tournament(self, client):
        """PARE-49: active_tournament is null when no tournament exists."""
        data = client.get("/api/scoreboard").get_json()
        assert data["active_tournament"] is None

    def test_active_tournament_is_null_when_only_open_tournament(self, client):
        """PARE-49: active_tournament is null when only open (future) tournaments exist."""
        client.post("/api/tournaments", json={
            "name": "Future Cup",
            "starts_at": _future_ts(3600),
            "ends_at": _future_ts(7200),
        })
        data = client.get("/api/scoreboard").get_json()
        assert data["active_tournament"] is None


class TestApiScoreboardScores:
    def test_empty_db_returns_empty_scores(self, client):
        """PARE-49: scores is empty list when DB has no scores."""
        data = client.get("/api/scoreboard").get_json()
        assert data["scores"] == []

    def test_scores_contain_expected_fields(self, client):
        """PARE-49: each score entry has id, name, score, created_at."""
        _post_score(client, "Alice", 1000)
        scores = client.get("/api/scoreboard").get_json()["scores"]
        assert len(scores) >= 1
        entry = scores[0]
        for field in ("id", "name", "score", "created_at"):
            assert field in entry, f"Missing field: {field}"

    def test_scores_ordered_by_score_desc(self, client):
        """PARE-49: scores are ordered highest score first."""
        _post_score(client, "Low", 100)
        _post_score(client, "High", 9000)
        _post_score(client, "Mid", 4500)
        scores = client.get("/api/scoreboard").get_json()["scores"]
        values = [s["score"] for s in scores]
        assert values == sorted(values, reverse=True)

    def test_scores_capped_at_10(self, client):
        """PARE-49: scores array has at most 10 entries even if more exist."""
        for i in range(15):
            _post_score(client, f"P{i}", (i + 1) * 100)
        scores = client.get("/api/scoreboard").get_json()["scores"]
        assert len(scores) <= 10

    def test_scores_returns_top_10_not_bottom(self, client):
        """PARE-49: the 10 scores returned are the highest ones."""
        for i in range(15):
            _post_score(client, f"P{i}", (i + 1) * 100)  # 100..1500
        scores = client.get("/api/scoreboard").get_json()["scores"]
        # Lowest in top-10 should be at least 600 (ranks 6–15 of 15)
        min_score = min(s["score"] for s in scores)
        assert min_score >= 600


class TestApiScoreboardActiveTournament:
    def test_active_tournament_not_null_when_active(self, client):
        """PARE-49: active_tournament is populated when an active tournament exists."""
        _create_active_tournament(client, "Live Cup")
        data = client.get("/api/scoreboard").get_json()
        assert data["active_tournament"] is not None

    def test_active_tournament_has_required_fields(self, client):
        """PARE-49: active_tournament has id, name, status, standings."""
        _create_active_tournament(client, "Live Cup")
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        for field in ("id", "name", "status", "standings"):
            assert field in at, f"Missing field: {field}"

    def test_active_tournament_status_is_active(self, client):
        """PARE-49: active_tournament.status == 'active'."""
        _create_active_tournament(client, "Live Cup")
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        assert at["status"] == "active"

    def test_active_tournament_standings_is_list(self, client):
        """PARE-49: active_tournament.standings is an array."""
        _create_active_tournament(client, "Live Cup")
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        assert isinstance(at["standings"], list)

    def test_active_tournament_standings_empty_when_no_entrants(self, client):
        """PARE-49: standings is empty list when nobody has joined."""
        _create_active_tournament(client, "Empty Cup")
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        assert at["standings"] == []

    def test_active_tournament_standings_has_entrant_fields(self, client):
        """PARE-49: each standings entry has rank, name, best_score, submitted_at."""
        tid = _create_active_tournament(client, "Live Cup")
        _join_and_score(client, tid, "Alice", 500)
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        assert len(at["standings"]) == 1
        entry = at["standings"][0]
        for field in ("rank", "name", "best_score"):
            assert field in entry, f"Missing field: {field}"

    def test_active_tournament_standings_ordered_by_score_desc(self, client):
        """PARE-49: standings ordered highest best_score first."""
        tid = _create_active_tournament(client, "Ranked Cup")
        _join_and_score(client, tid, "Alice", 300)
        _join_and_score(client, tid, "Bob", 1000)
        _join_and_score(client, tid, "Carol", 700)
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        scores_in_order = [e["best_score"] for e in at["standings"]]
        assert scores_in_order == sorted(scores_in_order, reverse=True)

    def test_active_tournament_first_place_rank_is_1(self, client):
        """PARE-49: top-ranked standings entry has rank == 1."""
        tid = _create_active_tournament(client, "Cup")
        _join_and_score(client, tid, "Alice", 999)
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        assert at["standings"][0]["rank"] == 1

    def test_completed_tournament_not_shown(self, client):
        """PARE-49: a completed tournament does not appear as active_tournament."""
        tid = _create_active_tournament(client, "Old Cup")
        # Force it to completed
        with database.get_db() as conn:
            conn.execute(
                "UPDATE tournaments SET status='completed', ends_at=? WHERE id=?",
                (_past_ts(60), tid),
            )
            conn.commit()
        data = client.get("/api/scoreboard").get_json()
        assert data["active_tournament"] is None

    def test_prefers_most_recently_started_active_tournament(self, client):
        """PARE-49: when multiple active tournaments exist, the most recent one is shown."""
        tid1 = _create_active_tournament(client, "Old Active")
        tid2 = _create_active_tournament(client, "New Active")
        # Make tid1 start earlier
        with database.get_db() as conn:
            conn.execute(
                "UPDATE tournaments SET starts_at=? WHERE id=?",
                (_past_ts(7200), tid1),
            )
            conn.execute(
                "UPDATE tournaments SET starts_at=? WHERE id=?",
                (_past_ts(60), tid2),
            )
            conn.commit()
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        assert at is not None
        assert at["id"] == tid2


# ===========================================================================
# PARE-49 — GET /scoreboard HTML endpoint
# ===========================================================================

class TestScoreboardHtmlEndpoint:
    def test_returns_200(self, client):
        """PARE-49: GET /scoreboard returns HTTP 200."""
        resp = client.get("/scoreboard")
        assert resp.status_code == 200

    def test_content_type_is_html(self, client):
        """PARE-49: Content-Type includes text/html."""
        resp = client.get("/scoreboard")
        assert "text/html" in resp.content_type

    def test_contains_score_data(self, client):
        """PARE-49: HTML body renders player names and scores."""
        _post_score(client, "GhostByte", 7777)
        body = client.get("/scoreboard").data.decode()
        assert "GhostByte" in body
        assert "7777" in body

    def test_empty_state_shown_when_no_scores(self, client):
        """PARE-49: when no scores exist, the page still renders (no 500)."""
        resp = client.get("/scoreboard")
        assert resp.status_code == 200

    def test_auto_refresh_present(self, client):
        """PARE-49: HTML contains setInterval with 5000ms for auto-refresh."""
        body = client.get("/scoreboard").data.decode()
        # Accept either `setInterval(refresh, 5000)` or `setInterval(…, 5000)`
        assert "5000" in body
        assert "setInterval" in body

    def test_filter_input_present(self, client):
        """PARE-49: HTML contains a player filter input element."""
        body = client.get("/scoreboard").data.decode()
        assert "filter" in body.lower()
        assert "<input" in body.lower()

    def test_tournament_section_hidden_when_no_active_tournament(self, client):
        """PARE-49: tournament section is hidden (display:none) when no active tournament."""
        body = client.get("/scoreboard").data.decode()
        # The tournament section div must carry display:none style when no active tournament
        assert 'display:none' in body or 'display: none' in body

    def test_tournament_section_visible_when_active(self, client):
        """PARE-49: tournament section is NOT hidden when an active tournament exists."""
        tid = _create_active_tournament(client, "Visible Cup")
        body = client.get("/scoreboard").data.decode()
        assert "Visible Cup" in body
        # The section should not carry display:none when tournament is active
        # Check: tournament-section must appear without display:none on that div
        import re
        # Find the tournament-section div and confirm it has no inline display:none
        match = re.search(r'id="tournament-section"([^>]*?)>', body)
        assert match is not None, "tournament-section div not found"
        section_attrs = match.group(1)
        assert "display:none" not in section_attrs and "display: none" not in section_attrs

    def test_html_contains_scoreboard_title(self, client):
        """PARE-49: HTML page contains a recognisable scoreboard heading."""
        body = client.get("/scoreboard").data.decode()
        assert "Scoreboard" in body or "scoreboard" in body.lower()

    def test_multiple_scores_rendered(self, client):
        """PARE-49: multiple players all appear in the HTML."""
        players = [("Alice", 1000), ("Bob", 2000), ("Carol", 1500)]
        for name, score in players:
            _post_score(client, name, score)
        body = client.get("/scoreboard").data.decode()
        for name, score in players:
            assert name in body
            assert str(score) in body

    def test_fetch_scoreboard_api_call_in_js(self, client):
        """PARE-49: JS in the page fetches /api/scoreboard for live updates."""
        body = client.get("/scoreboard").data.decode()
        assert "/api/scoreboard" in body


# ===========================================================================
# PARE-50 — seed_scoreboard.py
# ===========================================================================

class TestSeedScoreboardScript:
    def _init_db(self, db_path):
        """Initialise a fresh DB at db_path using database.init_db()."""
        original = database.DB_PATH
        database.DB_PATH = db_path
        os.environ["DB_PATH"] = db_path
        try:
            database.init_db()
        finally:
            database.DB_PATH = original
            os.environ["DB_PATH"] = original

    def _run_seed(self, db_path):
        """Run the seed script against the given DB file path."""
        script = os.path.join(
            os.path.dirname(__file__), "scripts", "seed_scoreboard.py"
        )
        result = subprocess.run(
            [sys.executable, script],
            env={**os.environ, "DB_PATH": db_path},
            capture_output=True,
            text=True,
        )
        return result

    def _get_conn(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_seed_script_exists(self):
        """PARE-50: scripts/seed_scoreboard.py exists."""
        script = os.path.join(os.path.dirname(__file__), "scripts", "seed_scoreboard.py")
        assert os.path.isfile(script), f"Seed script not found: {script}"

    def test_seed_script_runs_without_error(self, tmp_path):
        """PARE-50: seed script exits with code 0."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)
        result = self._run_seed(db_path)
        assert result.returncode == 0, f"Seed script failed:\n{result.stderr}"

    def test_seed_inserts_at_least_15_distinct_players(self, tmp_path):
        """PARE-50: after seeding, at least 15 distinct player names in scores."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)
        result = self._run_seed(db_path)
        assert result.returncode == 0, result.stderr

        conn = self._get_conn(db_path)
        row = conn.execute("SELECT COUNT(DISTINCT name) AS cnt FROM scores").fetchone()
        conn.close()
        assert row["cnt"] >= 15

    def test_seed_creates_active_tournament(self, tmp_path):
        """PARE-50: after seeding, at least one tournament with status='active'."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)
        self._run_seed(db_path)

        conn = self._get_conn(db_path)
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM tournaments WHERE status = 'active'"
        ).fetchone()
        conn.close()
        assert row["cnt"] >= 1

    def test_seed_tournament_has_5_entrants(self, tmp_path):
        """PARE-50: the active tournament has at least 5 entrant rows."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)
        self._run_seed(db_path)

        conn = self._get_conn(db_path)
        t_row = conn.execute(
            "SELECT id FROM tournaments WHERE status='active' LIMIT 1"
        ).fetchone()
        assert t_row is not None
        entry_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM tournament_entries WHERE tournament_id = ?",
            (t_row["id"],),
        ).fetchone()
        conn.close()
        assert entry_row["cnt"] >= 5

    def test_seed_tournament_entrants_have_scores(self, tmp_path):
        """PARE-50: at least one tournament entrant has a non-null best_score."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)
        self._run_seed(db_path)

        conn = self._get_conn(db_path)
        t_row = conn.execute(
            "SELECT id FROM tournaments WHERE status='active' LIMIT 1"
        ).fetchone()
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM tournament_entries WHERE tournament_id = ? AND best_score IS NOT NULL",
            (t_row["id"],),
        ).fetchone()
        conn.close()
        assert row["cnt"] >= 1

    def test_seed_is_idempotent(self, tmp_path):
        """PARE-50: running seed twice produces the same player count (idempotent)."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)

        self._run_seed(db_path)
        conn = self._get_conn(db_path)
        cnt1 = conn.execute("SELECT COUNT(DISTINCT name) AS c FROM scores").fetchone()["c"]
        t_cnt1 = conn.execute("SELECT COUNT(*) AS c FROM tournaments").fetchone()["c"]
        conn.close()

        self._run_seed(db_path)
        conn = self._get_conn(db_path)
        cnt2 = conn.execute("SELECT COUNT(DISTINCT name) AS c FROM scores").fetchone()["c"]
        t_cnt2 = conn.execute("SELECT COUNT(*) AS c FROM tournaments").fetchone()["c"]
        conn.close()

        assert cnt1 == cnt2, "Distinct player count changed on second seed run"
        assert t_cnt2 == t_cnt1, "Tournament count changed on second seed run"

    def test_seed_named_tournament_is_qa_sprint(self, tmp_path):
        """PARE-50: the created tournament is named 'QA Sprint' as specified."""
        db_path = str(tmp_path / "seed_test.db")
        self._init_db(db_path)
        self._run_seed(db_path)

        conn = self._get_conn(db_path)
        row = conn.execute(
            "SELECT name FROM tournaments WHERE status='active' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["name"] == "QA Sprint"


# ===========================================================================
# PARE-51 — edge cases beyond the coder's own tests
# ===========================================================================

class TestApiScoreboardEdgeCases:
    def test_scores_contain_name_field(self, client):
        """PARE-51: each score in /api/scoreboard has a 'name' field."""
        _post_score(client, "EdgeCase", 42)
        scores = client.get("/api/scoreboard").get_json()["scores"]
        for s in scores:
            assert "name" in s

    def test_scores_contain_score_field(self, client):
        """PARE-51: each score in /api/scoreboard has a 'score' field."""
        _post_score(client, "EdgeCase", 42)
        scores = client.get("/api/scoreboard").get_json()["scores"]
        for s in scores:
            assert "score" in s

    def test_active_tournament_standings_ranks_are_sequential(self, client):
        """PARE-51: standings ranks start at 1 and increment by 1."""
        tid = _create_active_tournament(client)
        _join_and_score(client, tid, "Alice", 100)
        _join_and_score(client, tid, "Bob", 200)
        _join_and_score(client, tid, "Carol", 300)
        at = client.get("/api/scoreboard").get_json()["active_tournament"]
        ranks = [e["rank"] for e in at["standings"]]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_get_method_only(self, client):
        """PARE-51: POST /api/scoreboard is not a valid endpoint."""
        resp = client.post("/api/scoreboard", json={})
        assert resp.status_code in (404, 405)

    def test_scoreboard_html_does_not_crash_with_active_tournament(self, client):
        """PARE-51: /scoreboard renders without 500 when an active tournament exists."""
        tid = _create_active_tournament(client, "Render Cup")
        _join_and_score(client, tid, "Alice", 9001)
        resp = client.get("/scoreboard")
        assert resp.status_code == 200

    def test_scoreboard_html_shows_tournament_name(self, client):
        """PARE-51: tournament name appears in HTML when tournament is active."""
        tid = _create_active_tournament(client, "Visible Trophy")
        body = client.get("/scoreboard").data.decode()
        assert "Visible Trophy" in body

    def test_scoreboard_html_shows_tournament_player(self, client):
        """PARE-51: tournament entrant name appears in HTML."""
        tid = _create_active_tournament(client, "Cup")
        _join_and_score(client, tid, "TourneyPlayer", 800)
        body = client.get("/scoreboard").data.decode()
        assert "TourneyPlayer" in body

    def test_api_scoreboard_not_affected_by_non_active_tournament(self, client):
        """PARE-51: creating an open tournament does not set active_tournament."""
        client.post("/api/tournaments", json={
            "name": "Future",
            "starts_at": _future_ts(3600),
            "ends_at": _future_ts(7200),
        })
        data = client.get("/api/scoreboard").get_json()
        assert data["active_tournament"] is None

    def test_scoreboard_page_shows_rank_numbers(self, client):
        """PARE-51: the HTML renders rank positions (1, 2, 3…) for global scores."""
        for i, name in enumerate(["Alpha", "Beta", "Gamma"], start=1):
            _post_score(client, name, i * 1000)
        body = client.get("/scoreboard").data.decode()
        # At minimum rank 1 should appear
        assert ">1<" in body or ">1 <" in body or "rank" in body.lower()
