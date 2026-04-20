from flask import Flask, render_template, jsonify, request
from datetime import datetime, timezone
import database

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({"status": "ok"})


@app.route('/api/scores', methods=['GET'])
def get_scores():
    name = request.args.get('name')
    raw_limit = request.args.get('limit', '10')
    raw_offset = request.args.get('offset', '0')

    try:
        limit = int(raw_limit)
        offset = int(raw_offset)
    except (ValueError, TypeError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    if limit < 0 or offset < 0:
        return jsonify({"error": "limit and offset must be non-negative"}), 400
    limit = min(limit, 100)

    if name is not None:
        sql = 'SELECT id, name, score, created_at FROM scores WHERE name = ? ORDER BY score DESC LIMIT ? OFFSET ?'
        params = (name, limit, offset)
    else:
        sql = 'SELECT id, name, score, created_at FROM scores ORDER BY score DESC LIMIT ? OFFSET ?'
        params = (limit, offset)

    with database.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route('/api/scores/<int:score_id>', methods=['GET'])
def get_score_by_id(score_id):
    with database.get_db() as conn:
        row = conn.execute(
            'SELECT id, name, score, created_at FROM scores WHERE id = ?',
            (score_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "score not found"}), 404
    return jsonify(dict(row))


@app.route('/api/players', methods=['GET'])
def get_players():
    with database.get_db() as conn:
        rows = conn.execute('''
            SELECT
                name,
                MAX(score)   AS best_score,
                COUNT(*)     AS total_games,
                AVG(score)   AS avg_score
            FROM scores
            GROUP BY name
            ORDER BY best_score DESC
        ''').fetchall()
    return jsonify([dict(row) for row in rows])


@app.route('/api/players/<name>', methods=['GET'])
def get_player_profile(name):
    with database.get_db() as conn:
        player_row = conn.execute('''
            SELECT
                name,
                MAX(score)   AS best_score,
                COUNT(*)     AS total_games,
                AVG(score)   AS avg_score
            FROM scores
            WHERE name = ?
            GROUP BY name
        ''', (name,)).fetchone()

        if player_row is None:
            return jsonify({"error": "player not found"}), 404

        rank_row = conn.execute('''
            SELECT COUNT(*) + 1 AS rank
            FROM (
                SELECT name, MAX(score) AS best_score
                FROM scores
                GROUP BY name
            )
            WHERE best_score > ?
        ''', (player_row['best_score'],)).fetchone()

        recent = conn.execute('''
            SELECT id, score, created_at
            FROM scores
            WHERE name = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (name,)).fetchall()

    return jsonify({
        "name": player_row['name'],
        "rank": rank_row['rank'],
        "best_score": player_row['best_score'],
        "avg_score": player_row['avg_score'],
        "total_games": player_row['total_games'],
        "recent_scores": [dict(r) for r in recent],
    })


@app.route('/api/scores', methods=['POST'])
def post_score():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "request body must be valid JSON"}), 400

    name = data.get('name')
    score = data.get('score')

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 422

    if not isinstance(score, int) or isinstance(score, bool) or score <= 0:
        return jsonify({"error": "score must be a positive integer"}), 422

    with database.get_db() as conn:
        cursor = conn.execute(
            'INSERT INTO scores (name, score) VALUES (?, ?)',
            (name.strip(), score)
        )
        conn.commit()
        row = conn.execute(
            'SELECT id, name, score, created_at FROM scores WHERE id = ?',
            (cursor.lastrowid,)
        ).fetchone()

    return jsonify(dict(row)), 201


# ---------------------------------------------------------------------------
# Tournament helpers
# ---------------------------------------------------------------------------

def _maybe_activate_tournament(conn, tournament_id, current_status, starts_at):
    """Lazily transition open -> active if starts_at has passed."""
    if current_status == 'open':
        now = datetime.now(timezone.utc).isoformat()
        if starts_at <= now:
            conn.execute(
                "UPDATE tournaments SET status = 'active' WHERE id = ?",
                (tournament_id,)
            )
            conn.commit()
            return 'active'
    return current_status


def _tournament_row_with_status(conn, row):
    """Return a dict for a tournament row with dynamic status applied."""
    d = dict(row)
    d['status'] = _maybe_activate_tournament(conn, d['id'], d['status'], d['starts_at'])
    return d


def _get_standings(conn, tournament_id):
    rows = conn.execute('''
        SELECT name, best_score, submitted_at
        FROM tournament_entries
        WHERE tournament_id = ?
        ORDER BY best_score DESC NULLS LAST
    ''', (tournament_id,)).fetchall()
    standings = []
    for i, row in enumerate(rows):
        standings.append({
            "rank": i + 1,
            "name": row['name'],
            "best_score": row['best_score'],
            "submitted_at": row['submitted_at'],
        })
    return standings


# ---------------------------------------------------------------------------
# Tournament routes
# ---------------------------------------------------------------------------

@app.route('/api/tournaments', methods=['POST'])
def create_tournament():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "request body must be valid JSON"}), 400

    name = data.get('name')
    starts_at = data.get('starts_at')
    ends_at = data.get('ends_at')

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400
    if not isinstance(starts_at, str) or not starts_at.strip():
        return jsonify({"error": "starts_at is required"}), 400
    if not isinstance(ends_at, str) or not ends_at.strip():
        return jsonify({"error": "ends_at is required"}), 400
    if ends_at <= starts_at:
        return jsonify({"error": "ends_at must be after starts_at"}), 400

    now = datetime.now(timezone.utc).isoformat()
    if starts_at <= now:
        return jsonify({"error": "starts_at must be in the future"}), 400

    created_at = now
    with database.get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tournaments (name, status, starts_at, ends_at, created_at) VALUES (?, 'open', ?, ?, ?)",
            (name.strip(), starts_at, ends_at, created_at)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()
    return jsonify(dict(row)), 201


@app.route('/api/tournaments', methods=['GET'])
def list_tournaments():
    status_filter = request.args.get('status')
    with database.get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments ORDER BY starts_at DESC"
        ).fetchall()
        results = []
        for row in rows:
            t = _tournament_row_with_status(conn, row)
            if status_filter is None or t['status'] == status_filter:
                results.append(t)
    return jsonify(results)


@app.route('/api/tournaments/<int:tournament_id>', methods=['GET'])
def get_tournament(tournament_id):
    with database.get_db() as conn:
        row = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "tournament not found"}), 404
        t = _tournament_row_with_status(conn, row)
        t['standings'] = _get_standings(conn, tournament_id)
    return jsonify(t)


@app.route('/api/tournaments/<int:tournament_id>/join', methods=['POST'])
def join_tournament(tournament_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "request body must be valid JSON"}), 400

    name = data.get('name')
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400
    name = name.strip()

    with database.get_db() as conn:
        row = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "tournament not found"}), 404

        t = _tournament_row_with_status(conn, row)
        if t['status'] == 'completed':
            return jsonify({"error": "tournament is completed"}), 422

        # Check if already joined (idempotent)
        existing = conn.execute(
            "SELECT id, tournament_id, name, best_score, submitted_at, joined_at FROM tournament_entries WHERE tournament_id = ? AND name = ?",
            (tournament_id, name)
        ).fetchone()
        if existing:
            return jsonify(dict(existing)), 200

        joined_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO tournament_entries (tournament_id, name, joined_at) VALUES (?, ?, ?)",
            (tournament_id, name, joined_at)
        )
        conn.commit()
        entry = conn.execute(
            "SELECT id, tournament_id, name, best_score, submitted_at, joined_at FROM tournament_entries WHERE tournament_id = ? AND name = ?",
            (tournament_id, name)
        ).fetchone()
    return jsonify(dict(entry)), 201


@app.route('/api/tournaments/<int:tournament_id>/score', methods=['POST'])
def submit_tournament_score(tournament_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "request body must be valid JSON"}), 400

    name = data.get('name')
    score = data.get('score')

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400
    name = name.strip()

    if not isinstance(score, int) or isinstance(score, bool) or score <= 0:
        return jsonify({"error": "score must be a positive integer"}), 422

    with database.get_db() as conn:
        row = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "tournament not found"}), 404

        t = _tournament_row_with_status(conn, row)
        if t['status'] != 'active':
            return jsonify({"error": "tournament is not active"}), 422

        entry = conn.execute(
            "SELECT id, tournament_id, name, best_score, submitted_at, joined_at FROM tournament_entries WHERE tournament_id = ? AND name = ?",
            (tournament_id, name)
        ).fetchone()
        if entry is None:
            return jsonify({"error": "player has not joined this tournament"}), 409

        # Only update best_score if the new score is higher
        if entry['best_score'] is None or score > entry['best_score']:
            submitted_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE tournament_entries SET best_score = ?, submitted_at = ? WHERE tournament_id = ? AND name = ?",
                (score, submitted_at, tournament_id, name)
            )
            conn.commit()

        updated = conn.execute(
            "SELECT id, tournament_id, name, best_score, submitted_at, joined_at FROM tournament_entries WHERE tournament_id = ? AND name = ?",
            (tournament_id, name)
        ).fetchone()
    return jsonify(dict(updated)), 200


@app.route('/api/tournaments/<int:tournament_id>/complete', methods=['POST'])
def complete_tournament(tournament_id):
    with database.get_db() as conn:
        row = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "tournament not found"}), 404

        t = _tournament_row_with_status(conn, row)
        if t['status'] == 'completed':
            return jsonify({"error": "tournament is already completed"}), 422

        now = datetime.now(timezone.utc).isoformat()
        if now < t['ends_at']:
            return jsonify({"error": "cannot complete tournament before ends_at"}), 422

        conn.execute(
            "UPDATE tournaments SET status = 'completed' WHERE id = ?",
            (tournament_id,)
        )
        conn.commit()
        t['status'] = 'completed'
        t['standings'] = _get_standings(conn, tournament_id)
    return jsonify(t)


# ---------------------------------------------------------------------------
# Scoreboard helpers & routes
# ---------------------------------------------------------------------------

def get_scoreboard_data():
    """Return scoreboard data dict shared by /api/scoreboard and /scoreboard."""
    with database.get_db() as conn:
        # Top-10 global scores
        score_rows = conn.execute(
            'SELECT id, name, score, created_at FROM scores ORDER BY score DESC LIMIT 10'
        ).fetchall()
        scores = [dict(r) for r in score_rows]

        # First active tournament
        tournament_rows = conn.execute(
            'SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments ORDER BY starts_at DESC'
        ).fetchall()
        active_tournament = None
        for row in tournament_rows:
            t = _tournament_row_with_status(conn, row)
            if t['status'] == 'active':
                t['standings'] = _get_standings(conn, t['id'])
                active_tournament = t
                break

    return {'scores': scores, 'active_tournament': active_tournament}


@app.route('/api/scoreboard', methods=['GET'])
def api_scoreboard():
    return jsonify(get_scoreboard_data())


@app.route('/scoreboard', methods=['GET'])
def scoreboard():
    data = get_scoreboard_data()
    return render_template('scoreboard.html', **data)


@app.route('/tournaments', methods=['GET'])
def tournaments_page():
    with database.get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments ORDER BY starts_at DESC"
        ).fetchall()
        tournaments = [_tournament_row_with_status(conn, row) for row in rows]
    return render_template('tournaments.html', tournaments=tournaments)



# ---------------------------------------------------------------------------
# PARE-52 — Individual player history page
# ---------------------------------------------------------------------------

@app.route('/api/player/<name>', methods=['GET'])
def get_player_history(name):
    with database.get_db() as conn:
        scores_rows = conn.execute(
            'SELECT score, created_at FROM scores WHERE name = ? ORDER BY created_at DESC',
            (name,)
        ).fetchall()

        if not scores_rows:
            return jsonify({"error": "player not found"}), 404

        scores_list = [dict(row) for row in scores_rows]
        total_games = len(scores_list)
        best_score = max(r['score'] for r in scores_list)
        average_score = sum(r['score'] for r in scores_list) / total_games

    return jsonify({
        "name": name,
        "scores": scores_list,
        "total_games": total_games,
        "best_score": best_score,
        "average_score": round(average_score, 2),
    })


@app.route('/player/<name>', methods=['GET'])
def player_page(name):
    with database.get_db() as conn:
        scores_rows = conn.execute(
            'SELECT score, created_at FROM scores WHERE name = ? ORDER BY created_at DESC',
            (name,)
        ).fetchall()

        if not scores_rows:
            return render_template('player.html', player_name=name, not_found=True,
                                   scores=[], total_games=0, best_score=0, average_score=0)

        scores_list = [dict(row) for row in scores_rows]
        total_games = len(scores_list)
        best_score = max(r['score'] for r in scores_list)
        average_score = round(sum(r['score'] for r in scores_list) / total_games, 2)

    return render_template(
        'player.html',
        player_name=name,
        not_found=False,
        scores=scores_list,
        total_games=total_games,
        best_score=best_score,
        average_score=average_score,
    )


# ---------------------------------------------------------------------------
# PARE-53 — Game history page
# ---------------------------------------------------------------------------

def _time_ago(created_at_str):
    """Return a human-readable relative time string (e.g. '2 hours ago')."""
    try:
        dt = datetime.fromisoformat(created_at_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())
        if diff < 60:
            return f"{diff} second{'s' if diff != 1 else ''} ago"
        elif diff < 3600:
            mins = diff // 60
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        elif diff < 86400:
            hours = diff // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = diff // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return created_at_str


@app.route('/api/history', methods=['GET'])
def api_history():
    raw_limit = request.args.get('limit', '20')
    try:
        limit = int(raw_limit)
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer"}), 400
    if limit < 0:
        return jsonify({"error": "limit must be non-negative"}), 400
    limit = min(limit, 100)
    with database.get_db() as conn:
        rows = conn.execute(
            'SELECT id, name, score, created_at FROM scores ORDER BY created_at DESC, id DESC LIMIT ?',
            (limit,)
        ).fetchall()
    results = []
    for row in rows:
        entry = dict(row)
        entry['time_ago'] = _time_ago(entry['created_at'])
        results.append(entry)
    return jsonify(results)


@app.route('/history', methods=['GET'])
def history_page():
    with database.get_db() as conn:
        rows = conn.execute(
            'SELECT id, name, score, created_at FROM scores ORDER BY created_at DESC, id DESC LIMIT 20',
        ).fetchall()
    entries = []
    for i, row in enumerate(rows):
        entry = dict(row)
        entry['rank'] = i + 1
        entry['time_ago'] = _time_ago(entry['created_at'])
        entries.append(entry)
    return render_template('history.html', entries=entries)


# ---------------------------------------------------------------------------
# PARE-54 — About page
# ---------------------------------------------------------------------------

def _get_about_data():
    """Return about data dict shared by /api/about and /about."""
    with database.get_db() as conn:
        total_players = conn.execute(
            'SELECT COUNT(DISTINCT name) FROM scores'
        ).fetchone()[0]
        total_scores = conn.execute(
            'SELECT COUNT(*) FROM scores'
        ).fetchone()[0]
        total_tournaments = conn.execute(
            'SELECT COUNT(*) FROM tournaments'
        ).fetchone()[0]
    return {
        'name': 'Game Score Tracker',
        'version': '1.0.0',
        'total_players': total_players,
        'total_scores': total_scores,
        'total_tournaments': total_tournaments,
    }


@app.route('/api/about', methods=['GET'])
def api_about():
    return jsonify(_get_about_data())


@app.route('/about', methods=['GET'])
def about_page():
    data = _get_about_data()
    return render_template('about.html', **data)


# ---------------------------------------------------------------------------
# Badge helpers
# ---------------------------------------------------------------------------

def _assign_badge(best_score):
    """Return badge string for a given best score, or None if below threshold."""
    if best_score >= 8000:
        return 'gold'
    elif best_score >= 5000:
        return 'silver'
    elif best_score >= 2000:
        return 'bronze'
    return None


def _get_badge_data():
    """Query DB and return list of {player, badge, best_score} dicts."""
    with database.get_db() as conn:
        rows = conn.execute(
            'SELECT name, MAX(score) AS best_score FROM scores GROUP BY name'
        ).fetchall()
    result = []
    for row in rows:
        badge = _assign_badge(row['best_score'])
        if badge is not None:
            result.append({
                'player': row['name'],
                'badge': badge,
                'best_score': row['best_score'],
            })
    return result


# ---------------------------------------------------------------------------
# Badge routes
# ---------------------------------------------------------------------------

@app.route('/api/badges', methods=['GET'])
def api_badges():
    """Return JSON array of {player, badge, best_score} for players with badges."""
    return jsonify(_get_badge_data())


@app.route('/badges', methods=['GET'])
def badges_page():
    """HTML badge grid with colored icons and count summary."""
    badges = _get_badge_data()
    gold_count = sum(1 for b in badges if b['badge'] == 'gold')
    silver_count = sum(1 for b in badges if b['badge'] == 'silver')
    bronze_count = sum(1 for b in badges if b['badge'] == 'bronze')
    return render_template(
        'badges.html',
        badges=badges,
        gold_count=gold_count,
        silver_count=silver_count,
        bronze_count=bronze_count,
    )


# ---------------------------------------------------------------------------
# PARE-67 — Player achievements system
# ---------------------------------------------------------------------------

MILESTONES = [
    ("First Blood", lambda total, best: total >= 1),
    ("Veteran",     lambda total, best: total >= 10),
    ("Champion",    lambda total, best: best >= 9000),
]


def _get_achievements_data():
    """Return list of {player, achievements, total_scores} dicts."""
    with database.get_db() as conn:
        rows = conn.execute(
            'SELECT name, COUNT(*) as total, MAX(score) as best FROM scores GROUP BY name'
        ).fetchall()
    result = []
    for row in rows:
        earned = [name for name, check in MILESTONES if check(row['total'], row['best'])]
        result.append({
            'player': row['name'],
            'achievements': earned,
            'total_scores': row['total'],
        })
    return result


@app.route('/api/achievements', methods=['GET'])
def api_achievements():
    """Return JSON array of {player, achievements, total_scores}."""
    return jsonify(_get_achievements_data())


@app.route('/achievements', methods=['GET'])
def achievements_page():
    """HTML table of players with checkmark icons for earned achievements."""
    data = _get_achievements_data()
    milestone_names = [name for name, _ in MILESTONES]
    return render_template('achievements.html', players=data, milestones=milestone_names)


# ---------------------------------------------------------------------------
# PARE-68 — Game statistics dashboard
# ---------------------------------------------------------------------------

def _get_stats_data():
    """Return aggregate stats dict for /api/stats and /stats."""
    with database.get_db() as conn:
        total_games = conn.execute('SELECT COUNT(*) FROM scores').fetchone()[0]
        total_players = conn.execute('SELECT COUNT(DISTINCT name) FROM scores').fetchone()[0]

        highest_row = conn.execute(
            'SELECT name, score FROM scores ORDER BY score DESC LIMIT 1'
        ).fetchone()
        highest_score = dict(highest_row) if highest_row else {'name': None, 'score': None}

        most_active_row = conn.execute(
            'SELECT name, COUNT(*) AS games_played FROM scores GROUP BY name ORDER BY games_played DESC LIMIT 1'
        ).fetchone()
        most_active_player = dict(most_active_row) if most_active_row else {'name': None, 'games_played': 0}

        avg_row = conn.execute('SELECT AVG(score) FROM scores').fetchone()[0]
        average_score = round(avg_row, 2) if avg_row is not None else 0

        scores_today = conn.execute(
            "SELECT COUNT(*) FROM scores WHERE date(created_at) = date('now')"
        ).fetchone()[0]

    return {
        'total_games': total_games,
        'total_players': total_players,
        'highest_score': highest_score,
        'most_active_player': most_active_player,
        'average_score': average_score,
        'scores_today': scores_today,
    }


@app.route('/api/stats', methods=['GET'])
def api_stats():
    return jsonify(_get_stats_data())


@app.route('/stats', methods=['GET'])
def stats_page():
    data = _get_stats_data()
    return render_template('stats.html', **data)


# ---------------------------------------------------------------------------
# PARE-69 — Player streak tracker
# ---------------------------------------------------------------------------

def _compute_streaks(player_days):
    """Given a list of date strings (YYYY-MM-DD) for one player, return (current, best)."""
    if not player_days:
        return 0, 0
    from datetime import date, timedelta
    days = sorted(set(player_days))
    current = 1
    best = 1
    streak = 1
    for i in range(1, len(days)):
        prev = date.fromisoformat(days[i - 1])
        curr = date.fromisoformat(days[i])
        if curr - prev == timedelta(days=1):
            streak += 1
        else:
            streak = 1
        if streak > best:
            best = streak
    today = date.today()
    last_played_date = date.fromisoformat(days[-1])
    diff = today - last_played_date
    if diff > timedelta(days=1):
        current = 0
    else:
        current = 1
        for i in range(len(days) - 1, 0, -1):
            curr = date.fromisoformat(days[i])
            prev = date.fromisoformat(days[i - 1])
            if curr - prev == timedelta(days=1):
                current += 1
            else:
                break
    return current, best


def _get_streaks_data():
    """Return list of {player, current_streak, best_streak, last_played} dicts."""
    with database.get_db() as conn:
        rows = conn.execute(
            "SELECT name, date(created_at) AS day FROM scores GROUP BY name, day ORDER BY name, day"
        ).fetchall()
    from collections import defaultdict
    player_days = defaultdict(list)
    for row in rows:
        player_days[row['name']].append(row['day'])
    result = []
    for player, days in player_days.items():
        current, best = _compute_streaks(days)
        result.append({
            'player': player,
            'current_streak': current,
            'best_streak': best,
            'last_played': days[-1] if days else None,
        })
    result.sort(key=lambda x: x['current_streak'], reverse=True)
    return result


@app.route('/api/streaks', methods=['GET'])
def api_streaks():
    """Return JSON array of player streak data."""
    return jsonify(_get_streaks_data())


@app.route('/streaks', methods=['GET'])
def streaks_page():
    """HTML table of player streaks sorted by current_streak DESC."""
    streaks = _get_streaks_data()
    return render_template('streaks.html', streaks=streaks)


# ---------------------------------------------------------------------------
# PARE-75 — Player profile page with stats
# ---------------------------------------------------------------------------

@app.route('/api/player/<name>/profile', methods=['GET'])
def get_player_profile_stats(name):
    """Return player profile JSON: name, rank, total_games, avg_score, top_scores."""
    with database.get_db() as conn:
        player_row = conn.execute('''
            SELECT
                name,
                MAX(score)   AS best_score,
                COUNT(*)     AS total_games,
                AVG(score)   AS avg_score
            FROM scores
            WHERE name = ?
            GROUP BY name
        ''', (name,)).fetchone()

        if player_row is None:
            return jsonify({"error": "player not found"}), 404

        rank_row = conn.execute('''
            SELECT COUNT(*) + 1 AS rank
            FROM (
                SELECT name, MAX(score) AS best_score
                FROM scores
                GROUP BY name
            )
            WHERE best_score > ?
        ''', (player_row['best_score'],)).fetchone()

        top_rows = conn.execute('''
            SELECT score, created_at
            FROM scores
            WHERE name = ?
            ORDER BY score DESC
            LIMIT 5
        ''', (name,)).fetchall()

    top_scores = [
        {
            "rank": i + 1,
            "score": r['score'],
            "date": r['created_at'],
        }
        for i, r in enumerate(top_rows)
    ]

    return jsonify({
        "name": player_row['name'],
        "rank": rank_row['rank'],
        "total_games": player_row['total_games'],
        "avg_score": player_row['avg_score'],
        "top_scores": top_scores,
    })


@app.route('/player/<name>/profile', methods=['GET'])
def player_profile_page(name):
    """HTML player profile page: heading, rank, total games, avg score, top-5 table."""
    with database.get_db() as conn:
        player_row = conn.execute('''
            SELECT
                name,
                MAX(score)   AS best_score,
                COUNT(*)     AS total_games,
                AVG(score)   AS avg_score
            FROM scores
            WHERE name = ?
            GROUP BY name
        ''', (name,)).fetchone()

        if player_row is None:
            return render_template(
                'player_profile.html',
                player_name=name,
                not_found=True,
                rank=None,
                total_games=0,
                avg_score=0,
                top_scores=[],
            )

        rank_row = conn.execute('''
            SELECT COUNT(*) + 1 AS rank
            FROM (
                SELECT name, MAX(score) AS best_score
                FROM scores
                GROUP BY name
            )
            WHERE best_score > ?
        ''', (player_row['best_score'],)).fetchone()

        top_rows = conn.execute('''
            SELECT score, created_at
            FROM scores
            WHERE name = ?
            ORDER BY score DESC
            LIMIT 5
        ''', (name,)).fetchall()

    top_scores = [
        {
            "rank": i + 1,
            "score": r['score'],
            "date": r['created_at'],
        }
        for i, r in enumerate(top_rows)
    ]

    return render_template(
        'player_profile.html',
        player_name=player_row['name'],
        not_found=False,
        rank=rank_row['rank'],
        total_games=player_row['total_games'],
        avg_score=round(player_row['avg_score'], 2),
        top_scores=top_scores,
    )


if __name__ == '__main__':
    database.init_db()
    app.run(debug=True, port=5000)
