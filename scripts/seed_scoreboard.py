"""
seed_scoreboard.py — Seed script for scoreboard visual QA.

Seeds 15 players with varied scores, creates one active "QA Sprint" tournament,
joins 5 players, and submits scores for them.

Idempotent: safe to run multiple times.

Usage:
    python scripts/seed_scoreboard.py

Environment:
    DB_PATH  — path to SQLite database file (default: game.db)
"""

import os
import sys
import sqlite3
from datetime import datetime, timezone, timedelta

# Allow running from repo root or scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.environ.get('DB_PATH', 'scores.db')

PLAYERS = [
    ("PixelKnight", [9800, 7400, 5200]),
    ("NeonRacer", [8750, 6100]),
    ("GhostByte", [7200, 3400]),
    ("VortexPilot", [6900]),
    ("CyberFox", [6500, 4800]),
    ("LaserWolf", [5900, 2200]),
    ("ShadowBit", [5400]),
    ("QuantumAce", [4900, 3300]),
    ("TurboHawk", [4500, 1800]),
    ("BlinkDash", [4200]),
    ("IronClad", [3800, 2900]),
    ("StormRider", [3500]),
    ("NovaStar", [3100, 1500]),
    ("ZeroGrav", [2800]),
    ("PulseMax", [2400]),
    ("VoltEdge", [900]),
]

TOURNAMENT_NAME = "QA Sprint"
TOURNAMENT_PLAYERS = ["PixelKnight", "NeonRacer", "GhostByte", "VortexPilot", "CyberFox"]
TOURNAMENT_SCORES = {
    "PixelKnight": 1500,
    "NeonRacer": 1200,
    "GhostByte": 980,
    "VortexPilot": 750,
    "CyberFox": 640,
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def seed_scores(conn):
    now = datetime.now(timezone.utc)
    inserted = 0
    for name, scores in PLAYERS:
        for i, score in enumerate(scores):
            created_at = (now - timedelta(hours=len(scores) - i)).isoformat()
            # Use INSERT OR IGNORE — idempotent if exact row already exists.
            # Since we don't have a unique constraint on (name, score), we check manually.
            existing = conn.execute(
                "SELECT id FROM scores WHERE name = ? AND score = ?", (name, score)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO scores (name, score, created_at) VALUES (?, ?, ?)",
                    (name, score, created_at),
                )
                inserted += 1
    conn.commit()
    print(f"  Scores: inserted {inserted} rows (skipped duplicates)")


def seed_tournament(conn):
    now = datetime.now(timezone.utc)
    starts_at = (now - timedelta(hours=1)).isoformat()
    ends_at = (now + timedelta(hours=1)).isoformat()

    # Find existing "QA Sprint" tournament that is active/open
    existing = conn.execute(
        "SELECT id, status FROM tournaments WHERE name = ?", (TOURNAMENT_NAME,)
    ).fetchone()

    if existing:
        tid = existing["id"]
        # Make sure it's active
        conn.execute(
            "UPDATE tournaments SET status = 'active', starts_at = ?, ends_at = ? WHERE id = ?",
            (starts_at, ends_at, tid),
        )
        conn.commit()
        print(f"  Tournament: updated existing '{TOURNAMENT_NAME}' (id={tid}) → active")
    else:
        created_at = now.isoformat()
        cur = conn.execute(
            "INSERT INTO tournaments (name, status, starts_at, ends_at, created_at) VALUES (?, 'active', ?, ?, ?)",
            (TOURNAMENT_NAME, starts_at, ends_at, created_at),
        )
        conn.commit()
        tid = cur.lastrowid
        print(f"  Tournament: created '{TOURNAMENT_NAME}' (id={tid})")

    return tid


def seed_entries(conn, tid):
    joined_at = datetime.now(timezone.utc).isoformat()
    for name in TOURNAMENT_PLAYERS:
        conn.execute(
            "INSERT OR IGNORE INTO tournament_entries (tournament_id, name, joined_at) VALUES (?, ?, ?)",
            (tid, name, joined_at),
        )
    conn.commit()
    print(f"  Entries: joined {len(TOURNAMENT_PLAYERS)} players to tournament id={tid}")

    submitted_at = datetime.now(timezone.utc).isoformat()
    for name, score in TOURNAMENT_SCORES.items():
        existing = conn.execute(
            "SELECT best_score FROM tournament_entries WHERE tournament_id = ? AND name = ?",
            (tid, name),
        ).fetchone()
        if existing is not None:
            current_best = existing["best_score"]
            if current_best is None or score > current_best:
                conn.execute(
                    "UPDATE tournament_entries SET best_score = ?, submitted_at = ? WHERE tournament_id = ? AND name = ?",
                    (score, submitted_at, tid, name),
                )
    conn.commit()
    print(f"  Scores: submitted tournament scores for {len(TOURNAMENT_SCORES)} players")


def main():
    print(f"Seeding database: {DB_PATH}")
    conn = get_conn()
    try:
        seed_scores(conn)
        tid = seed_tournament(conn)
        seed_entries(conn, tid)
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
