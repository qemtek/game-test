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
    # TODO: return top 10 scores from the database, ordered by score descending
    # Each entry should have: id, name, score, created_at
    return jsonify([])


@app.route('/api/scores', methods=['POST'])
def post_score():
    # TODO: accept JSON body {"name": str, "score": int}
    # Validate: name must be non-empty string, score must be integer > 0
    # Persist to database, return the saved entry with its id
    return jsonify({"error": "not implemented"}), 501


if __name__ == '__main__':
    database.init_db()
    app.run(debug=True, port=5000)
