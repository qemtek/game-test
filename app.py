from flask import Flask, render_template, jsonify, request
import database

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route('/api/scores', methods=['GET'])
def get_scores():
    with database.get_db() as conn:
        rows = conn.execute(
            'SELECT id, name, score, created_at FROM scores ORDER BY score DESC LIMIT 10'
        ).fetchall()
    return jsonify([dict(row) for row in rows])


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
