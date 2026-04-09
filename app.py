from flask import Flask, render_template, jsonify, request
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


if __name__ == '__main__':
    database.init_db()
    app.run(debug=True, port=5000)
