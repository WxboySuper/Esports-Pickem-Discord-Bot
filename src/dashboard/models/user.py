import sys
import os
from datetime import datetime
import sqlite3
import logging

# Update import path to use bot's database
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../bot'))
from utils.db import PickemDB

db = PickemDB()

def get_user_by_id(user_id):
    # TODO: Implement database connection
    return {"id": user_id, "name": f"User {user_id}"}

def get_leaderboard(guild_id=None, limit=10):
    """
    Get global or guild-specific leaderboard
    
    Args:
        guild_id (int, optional): Specific guild to get leaderboard for
        limit (int): Number of users to return
    """
    try:
        if guild_id:
            return db.get_leaderboard(guild_id, limit)
        
        # For global leaderboard, combine all guilds
        with sqlite3.connect(db.db_path) as conn:
            c = conn.cursor()
            return c.execute("""
                SELECT 
                    user_id,
                    COUNT(*) as total_picks,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_picks,
                    COUNT(DISTINCT guild_id) as guild_count
                FROM picks
                GROUP BY user_id
                ORDER BY ? DESC
                LIMIT ?
            """, ('correct_picks', limit,)).fetchall()
            
    except Exception as e:
        logging.error("Error getting leaderboard %s", e)
        return {
            'success': False,
            'error': str(e),
            'data': []
        }

def get_user_stats(user_id, guild_id=None):
    """Get user statistics globally or for specific guild"""
    try:
        if guild_id:
            return db.get_user_stats(guild_id, user_id)
        
        # For global stats
        with sqlite3.connect(db.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                WITH user_picks AS (
                    SELECT 
                        p.pick_id,
                        p.is_correct,
                        m.winner IS NOT NULL as is_completed
                    FROM picks p
                    JOIN matches m ON p.match_id = m.match_id
                    WHERE p.user_id = ?
                )
                SELECT 
                    COUNT(*) as total_picks,
                    SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed_picks,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_picks
                FROM user_picks
            """, (user_id,))
            
            result = c.fetchone()
            total_picks = result[0] or 0
            completed_picks = result[1] or 0
            correct_picks = result[2] or 0
            
            return {
                "total_picks": total_picks,
                "completed_picks": completed_picks,
                "correct_picks": correct_picks,
                "accuracy": correct_picks / completed_picks if completed_picks > 0 else 0
            }
            
    except Exception as e:
        print(f"Error getting user stats: {e}")
        return {
            "Success": False,
            "Error": str(e),
            "total_picks": 0,
            "completed_picks": 0,
            "correct_picks": 0,
            "accuracy": 0
        }
