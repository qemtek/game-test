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
    """HTML tournaments listing page."""
    with database.get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, status, starts_at, ends_at, created_at FROM tournaments ORDER BY starts_at DESC"
        ).fetchall()
        active_tournaments = []
        open_tournaments = []
        completed_tournaments = []
        for row in rows:
            t = _tournament_row_with_status(conn, row)
            t['standings'] = _get_standings(conn, t['id'])
            if t['status'] == 'active':
                active_tournaments.append(t)
            elif t['status'] == 'open':
                open_tournaments.append(t)
            else:
                completed_tournaments.append(t)
    return render_template(
        'tournaments.html',
        active_tournaments=active_tournaments,
        open_tournaments=open_tournaments,
        completed_tournaments=completed_tournaments,
    )


if __name__ == '__main__':
    database.init_db()
    app.run(debug=True, port=5000)
