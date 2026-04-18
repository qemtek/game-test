"""
PARE-53 — Game History Page: Tester-authored edge-case tests.

These supplement the coder's tests in test_api_scores.py with additional
boundary, ordering, field-shape, and UI-content checks.
"""
import re
import pytest
from datetime import datetime, timezone
from app import app as flask_app, _time_ago
import database as _database


# ---------------------------------------------------------------------------
# Fixtures — must use the same isolation pattern as test_api_scores.py
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point database.DB_PATH at a fresh temp file for each test (same pattern
    as test_api_scores.py) so no seed data leaks between tests."""
    db_file = tmp_path / "test_scores_t53.db"
    monkeypatch.setattr(_database, "DB_PATH", str(db_file))
    monkeypatch.setenv("DB_PATH", str(db_file))
    _database.init_db()
    yield


@pytest.fixture()
def client(isolated_db):
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def _post(client, name, score):
    return client.post("/api/scores", json={"name": name, "score": score})


# ---------------------------------------------------------------------------
# _time_ago unit tests — pure function, no DB needed
# ---------------------------------------------------------------------------

class TestTimeAgoHelper:
    """Unit tests for the _time_ago() helper function."""

    def _ts(self, seconds_ago):
        """Return an ISO string that is `seconds_ago` seconds in the past."""
        from datetime import timedelta
        dt = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        return dt.isoformat()

    def test_just_now_singular(self):
        """1 second ago → '1 second ago' (singular)."""
        result = _time_ago(self._ts(1))
        assert result == "1 second ago"

    def test_seconds_plural(self):
        """30 seconds ago → 'X seconds ago' (plural)."""
        result = _time_ago(self._ts(30))
        assert "seconds ago" in result

    def test_1_minute(self):
        """Exactly 60 seconds → '1 minute ago' (singular)."""
        result = _time_ago(self._ts(60))
        assert result == "1 minute ago"

    def test_minutes_plural(self):
        """90 seconds (1.5 min) → '1 minute ago'; 120 s → '2 minutes ago'."""
        assert _time_ago(self._ts(120)) == "2 minutes ago"

    def test_1_hour(self):
        """3600 seconds → '1 hour ago' (singular)."""
        result = _time_ago(self._ts(3600))
        assert result == "1 hour ago"

    def test_hours_plural(self):
        """7200 seconds → '2 hours ago'."""
        assert _time_ago(self._ts(7200)) == "2 hours ago"

    def test_1_day(self):
        """86400 seconds → '1 day ago' (singular)."""
        assert _time_ago(self._ts(86400)) == "1 day ago"

    def test_days_plural(self):
        """172800 seconds → '2 days ago'."""
        assert _time_ago(self._ts(172800)) == "2 days ago"

    def test_invalid_string_returns_original(self):
        """Unparseable string is returned as-is (no crash)."""
        bad = "not-a-date"
        assert _time_ago(bad) == bad

    def test_naive_datetime_string(self):
        """Naive datetime string (no tz) is treated as UTC — no crash."""
        naive = "2020-01-01 00:00:00"
        result = _time_ago(naive)
        assert "ago" in result   # should be many days/years ago


# ---------------------------------------------------------------------------
# GET /api/history — edge cases
# ---------------------------------------------------------------------------

class TestApiHistoryEdgeCases:
    """Additional boundary and field-shape tests for GET /api/history."""

    def test_negative_limit_returns_400(self, client):
        """Negative limit must return 400."""
        resp = client.get("/api/history?limit=-1")
        assert resp.status_code == 400

    def test_float_limit_returns_400(self, client):
        """Float limit string must return 400."""
        resp = client.get("/api/history?limit=5.5")
        assert resp.status_code == 400

    def test_entry_id_field_present(self, client):
        """Each entry must include an 'id' field."""
        _post(client, "Alice", 100)
        data = client.get("/api/history").get_json()
        assert "id" in data[0]

    def test_entry_id_is_integer(self, client):
        """The 'id' field must be an integer."""
        _post(client, "Alice", 100)
        data = client.get("/api/history").get_json()
        assert isinstance(data[0]["id"], int)

    def test_most_recent_entry_is_first(self, client):
        """The most recently submitted score should appear at index 0."""
        _post(client, "Alice", 100)
        _post(client, "Bob", 200)
        _post(client, "Carol", 300)
        data = client.get("/api/history").get_json()
        assert data[0]["name"] == "Carol"

    def test_history_not_sorted_by_score(self, client):
        """History is ordered by insertion time, NOT by score descending."""
        _post(client, "LowScore", 10)
        _post(client, "HighScore", 9999)
        data = client.get("/api/history").get_json()
        # HighScore was submitted last, so it must be first
        assert data[0]["name"] == "HighScore"

    def test_limit_1_returns_single_entry(self, client):
        """limit=1 returns exactly one entry."""
        for i in range(5):
            _post(client, f"P{i}", (i + 1) * 50)
        data = client.get("/api/history?limit=1").get_json()
        assert len(data) == 1

    def test_limit_exceeding_count_returns_all(self, client):
        """limit=50 when only 3 scores exist should return 3."""
        for i in range(3):
            _post(client, f"P{i}", (i + 1) * 10)
        data = client.get("/api/history?limit=50").get_json()
        assert len(data) == 3

    def test_time_ago_format_matches_pattern(self, client):
        """time_ago values must match the pattern '<number> <unit> ago'."""
        _post(client, "Alice", 500)
        data = client.get("/api/history").get_json()
        pattern = re.compile(r"^\d+ \w+ ago$")
        assert pattern.match(data[0]["time_ago"]), \
            f"Unexpected time_ago format: {data[0]['time_ago']!r}"

    def test_score_field_is_integer(self, client):
        """Score field must be a numeric integer, not a string."""
        _post(client, "Alice", 777)
        data = client.get("/api/history").get_json()
        assert isinstance(data[0]["score"], int)

    def test_name_field_is_string(self, client):
        """Name field must be a string."""
        _post(client, "Alice", 777)
        data = client.get("/api/history").get_json()
        assert isinstance(data[0]["name"], str)

    def test_content_type_is_json(self, client):
        """Response Content-Type must be application/json."""
        resp = client.get("/api/history")
        assert "application/json" in resp.content_type

    def test_multiple_entries_same_player(self, client):
        """Multiple entries for the same player are all returned."""
        for s in [100, 200, 300]:
            _post(client, "Alice", s)
        data = client.get("/api/history").get_json()
        alice_entries = [e for e in data if e["name"] == "Alice"]
        assert len(alice_entries) == 3

    def test_limit_100_is_inclusive(self, client):
        """Exactly 100 scores with limit=100 should return 100 (not capped further)."""
        for i in range(100):
            _post(client, f"P{i}", i + 1)
        data = client.get("/api/history?limit=100").get_json()
        assert len(data) == 100

    def test_default_limit_is_20(self, client):
        """Default limit without ?limit= param is 20."""
        for i in range(30):
            _post(client, f"P{i}", i + 1)
        data = client.get("/api/history").get_json()
        assert len(data) == 20


# ---------------------------------------------------------------------------
# GET /history HTML page — edge cases
# ---------------------------------------------------------------------------

class TestHistoryPageEdgeCases:
    """Additional HTML-page edge-case tests for /history."""

    def test_page_title_contains_history(self, client):
        """Page should include 'History' in the title or heading."""
        body = client.get("/history").data.decode("utf-8")
        assert "History" in body or "history" in body.lower()

    def test_page_has_table_headers(self, client):
        """Page should have column headers: name/player, score, and time/when."""
        body = client.get("/history").data.decode("utf-8").lower()
        assert "name" in body or "player" in body
        assert "score" in body
        # "when" or "time" or similar
        assert "when" in body or "time" in body or "ago" in body

    def test_navigation_link_back_to_home(self, client):
        """History page should have a link back to '/'."""
        body = client.get("/history").data.decode("utf-8")
        assert 'href="/"' in body or "href='/'" in body

    def test_multiple_players_all_shown(self, client):
        """All distinct player names should appear on /history."""
        _post(client, "Alice", 100)
        _post(client, "Bob", 200)
        _post(client, "Carol", 300)
        body = client.get("/history").data.decode("utf-8")
        assert "Alice" in body
        assert "Bob" in body
        assert "Carol" in body

    def test_rank_starts_at_1(self, client):
        """First row rank must be 1."""
        _post(client, "Alice", 100)
        _post(client, "Bob", 200)
        body = client.get("/history").data.decode("utf-8")
        # The rank "1" should appear before "2"
        pos1 = body.find(">1<")
        pos2 = body.find(">2<")
        assert pos1 != -1 and pos2 != -1
        assert pos1 < pos2

    def test_rows_ordered_most_recent_first(self, client):
        """First data row must be the most recently submitted score."""
        _post(client, "First", 100)
        _post(client, "Second", 200)
        _post(client, "Third", 300)
        body = client.get("/history").data.decode("utf-8")
        pos_third = body.find("Third")
        pos_first = body.find("First")
        assert pos_third < pos_first, \
            "Most recent entry ('Third') should appear before oldest ('First')"

    def test_score_values_appear_in_table(self, client):
        """Submitted score values must appear in the page body."""
        _post(client, "Alice", 4242)
        body = client.get("/history").data.decode("utf-8")
        assert "4242" in body

    def test_time_ago_appears_for_each_entry(self, client):
        """Each entry row must contain a 'ago' time string."""
        _post(client, "Alice", 100)
        _post(client, "Bob", 200)
        body = client.get("/history").data.decode("utf-8")
        ago_count = body.count("ago")
        assert ago_count >= 2

    def test_empty_state_no_error(self, client):
        """Empty /history page must return 200 (no 500 crash)."""
        resp = client.get("/history")
        assert resp.status_code == 200

    def test_returns_html_content_type(self, client):
        """Content-Type must be text/html."""
        resp = client.get("/history")
        assert "text/html" in resp.content_type

    def test_history_link_on_index_is_clickable(self, client):
        """Index page navigation link must use an <a href="/history"> element."""
        body = client.get("/").data.decode("utf-8")
        assert 'href="/history"' in body or "href='/history'" in body
