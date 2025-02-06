import sqlite3
from datetime import datetime

class Pick:
    DB_PATH = "pickem.db"  # Use the same database as the Discord bot

    @staticmethod
    def get_picks_by_user(user_id):
        with sqlite3.connect(Pick.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT p.*, m.team_a, m.team_b, m.winner
                FROM picks p
                JOIN matches m ON p.match_id = m.match_id
                WHERE p.user_id = ?
                ORDER BY p.created_at DESC
            """, (user_id,))
            return [dict(row) for row in c.fetchall()]

    @staticmethod
    def get_recent_picks(limit=10):
        with sqlite3.connect(Pick.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT p.*, m.team_a, m.team_b, m.winner
                FROM picks p
                JOIN matches m ON p.match_id = m.match_id
                ORDER BY p.created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in c.fetchall()]
