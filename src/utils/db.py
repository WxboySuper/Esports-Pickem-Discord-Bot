import sqlite3
import logging
from datetime import datetime
from .bot_instance import BotInstance
from pathlib import Path


def setup_db_logging():
    """Set up database logging"""
    # Set up logger
    logger = logging.getLogger('database')
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    logger.handlers.clear()

    # Configure logging format
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%d-%m %H:%M:%S"
    )

    # Set up file handler with a single log file
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'database.log'

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Initialize logger
db_logger = setup_db_logging()


class PickemDB:
    def __init__(self, db_path="pickem.db"):
        self.db_path = db_path
        self.announcer = None
        db_logger.info("Initializing database with path: %s", db_path)

        # Initialize tables first, then migrate
        try:
            # Create and store the connection at instance level
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0  # 30 seconds timeout
            )
            # Set busy timeout to handle concurrent access
            self._conn.execute('PRAGMA busy_timeout = 30000')  # 30 seconds in milliseconds
            self._cursor = self._conn.cursor()

            # Initialize tables using the stored connection
            self.init_db()
            self._conn.commit()  # Ensure changes are committed
            db_logger.info("Database tables initialized successfully")

            # Run migrations using the same connection
            self.migrate_db(self._conn)
            self._conn.commit()  # Ensure changes are committed
            db_logger.info("Database migrations completed successfully")
        except sqlite3.Error as e:
            db_logger.error("Database initialization failed: %s", e)
            raise

        # Try to get announcer from bot instance
        bot = BotInstance.get_bot()
        if bot:
            self.announcer = bot.announcer
            db_logger.debug("Announcer retrieved from bot instance")
        else:
            db_logger.warning("Failed to retrieve announcer from bot instance")

    def init_db(self):
        """Initialize database tables"""
        db_logger.info("Initializing database tables")
        try:
            # Use existing connection instead of creating new one
            self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS leagues (
                    league_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    region TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    match_id INTEGER PRIMARY KEY,
                    league_id INTEGER NOT NULL,
                    team_a TEXT NOT NULL,
                    team_b TEXT NOT NULL,
                    winner TEXT,
                    match_date TIMESTAMP,
                    match_name TEXT NOT NULL DEFAULT 'Groups',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (league_id) REFERENCES leagues (league_id)
                )
            ''')

            self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS picks (
                    pick_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    match_id INTEGER NOT NULL,
                    pick TEXT NOT NULL,
                    is_correct BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches (match_id),
                    UNIQUE(guild_id, user_id, match_id)
                )
            ''')
            self._conn.commit()

            # Insert default league if none exists
            self._cursor.execute("SELECT COUNT(*) FROM leagues")
            if self._cursor.fetchone()[0] == 0:
                self._cursor.execute("""
                    INSERT INTO leagues (name, description, region)
                    VALUES ('Default League', 'Default league for existing matches', 'Global')
                """)
                self._conn.commit()

        except sqlite3.Error as e:
            db_logger.error("Failed to initialize database tables: %s", e, exc_info=True)
            raise

    def migrate_db(self, conn=None):
        """Handle database migrations"""
        if conn is None:
            conn = self._conn

        try:
            c = conn.cursor()
            # Migration logic using provided connection
            # First verify/create the leagues table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leagues'")
            if not c.fetchone():
                c.execute('''
                    CREATE TABLE IF NOT EXISTS leagues (
                        league_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        region TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()

            # Create default league if none exists
            c.execute("SELECT COUNT(*) FROM leagues")
            if c.fetchone()[0] == 0:
                c.execute("""
                    INSERT INTO leagues (name, description, region)
                    VALUES ('Default League', 'Default league for existing matches', 'Global')
                """)
                conn.commit()

            # Get default league ID
            c.execute("SELECT league_id FROM leagues ORDER BY league_id LIMIT 1")
            default_league_id = c.fetchone()[0]

            # Check if matches table exists and get columns
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
            matches_exist = c.fetchone() is not None

            if matches_exist:
                # Get current columns in matches table
                res = c.execute("PRAGMA table_info(matches)")
                columns = [row[1] for row in res.fetchall()]

                # Handle migrations for existing matches table
                if 'league_id' not in columns:
                    c.execute("ALTER TABLE matches ADD COLUMN league_id INTEGER DEFAULT ?", (default_league_id,))

                if 'match_name' not in columns:
                    c.execute("ALTER TABLE matches ADD COLUMN match_name TEXT NOT NULL DEFAULT 'Groups'")

                if 'is_active' not in columns:
                    c.execute("ALTER TABLE matches ADD COLUMN is_active BOOLEAN DEFAULT 1")

            # Check picks table and add guild_id if needed
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='picks'")
            if c.fetchone():
                res = c.execute("PRAGMA table_info(picks)")
                columns = [row[1] for row in res.fetchall()]

                if 'guild_id' not in columns:
                    c.execute("ALTER TABLE picks ADD COLUMN guild_id INTEGER DEFAULT 0")

            conn.commit()

        except sqlite3.Error as e:
            db_logger.error("Migration failed: %s", e)
            raise

    def set_announcer(self, announcer):
        """Set the announcer for database events"""
        self.announcer = announcer

    def refresh_announcer(self):
        """Refresh announcer from bot instance"""
        bot = BotInstance.get_bot()
        if bot:
            self.announcer = bot.announcer
            return True
        return False

    async def handle_new_match(self, match_id: int, team_a: str, team_b: str, match_date: datetime, league_name: str):
        """Handle new match announcement"""
        if self.announcer and "tbd" not in team_a.lower() and "tbd" not in team_b.lower():
            await self.announcer.announce_new_match(match_id, team_a, team_b, match_date, league_name)

    def add_league(self, name: str, description: str, region: str) -> int:
        """Add a new league"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO leagues (name, description, region) VALUES (?, ?, ?)",
                (name, description, region)
            )
            conn.commit()
            return c.lastrowid

    def get_leagues(self, active_only: bool = True) -> list:
        """Get all leagues"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            query = "SELECT league_id, name, description, region, is_active FROM leagues"
            if active_only:
                query += " WHERE is_active = 1"
            return c.execute(query).fetchall()

    def update_league(self, league_id: int, name: str, description: str, region: str, is_active: bool) -> bool:
        """Update league details"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    UPDATE leagues
                    SET name = ?, description = ?, region = ?, is_active = ?
                    WHERE league_id = ?
                """, (name, description, region, is_active, league_id))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def add_match(self, league_id: int, team_a: str, team_b: str, match_date: datetime, is_active: int, match_name: str) -> int:
        """Add a new match to the database"""
        db_logger.info("Adding new match: %s vs %s (%s)", team_a, team_b, match_name)
        try:
            # Use class-level connection and cursor
            self._cursor.execute(
                "INSERT INTO matches (league_id, team_a, team_b, match_date, is_active, match_name) VALUES (?, ?, ?, ?, ?, ?)",
                (league_id, team_a, team_b, match_date, is_active, match_name)
            )
            self._conn.commit()
            match_id = self._cursor.lastrowid
            db_logger.info("Match created successfully with ID: %d", match_id)
            return match_id

        except sqlite3.Error as e:
            db_logger.error("Failed to add match: %s", e, exc_info=True)
            raise  # Raise the error instead of returning None

    def make_pick(self, guild_id: int, user_id: int, match_id: int, pick: str) -> bool:
        """Record a user's pick for a match"""
        try:
            db_logger.info(f"Recording pick: Guild {guild_id}, User {user_id}, Match {match_id}, Pick: {pick}")

            # First verify the match exists and is still pickable
            match = self.get_match_details(match_id)
            if not match:
                db_logger.warning(f"Match {match_id} not found")
                return False

            match_date = datetime.strptime(str(match['match_date']), '%Y-%m-%d %H:%M:%S')
            if match_date <= datetime.now():
                db_logger.warning(f"Match {match_id} has already started")
                return False

            # Use class-level connection instead of creating new one
            self._cursor.execute("""
                DELETE FROM picks
                WHERE guild_id = ? AND user_id = ? AND match_id = ?
            """, (guild_id, user_id, match_id))

            self._cursor.execute("""
                INSERT INTO picks (guild_id, user_id, match_id, pick)
                VALUES (?, ?, ?, ?)
            """, (guild_id, user_id, match_id, pick))

            self._conn.commit()
            db_logger.info("Pick recorded successfully")
            return True

        except Exception as e:
            db_logger.error(f"Database error: {str(e)}", exc_info=True)
            return False

    def update_match_result(self, match_id: int, winner: str) -> bool:
        """Update match result and calculate correct picks - globally"""
        db_logger.info("Updating match %d: Winner set to %s", match_id, winner)
        try:
            # Use instance connection and cursor instead of creating new ones
            self._cursor.execute(
                "UPDATE matches SET winner = ? WHERE match_id = ?",
                (winner, match_id)
            )
            self._cursor.execute("""
                UPDATE picks
                SET is_correct = (pick = ?)
                WHERE match_id = ?
            """, (winner, match_id))
            self._conn.commit()
            db_logger.info("Match %d result updated successfully", match_id)
            return True

        except sqlite3.Error as e:
            db_logger.error("Failed to update match result: %s", e, exc_info=True)
            return False

    def update_match(self, match_id: int, team_a: str, team_b: str, match_date: str | datetime, match_name: str) -> bool:
        """Update match details"""
        try:
            # Convert string to datetime if needed
            if isinstance(match_date, str):
                try:
                    match_date = datetime.strptime(match_date, '%Y-%m-%d %H:%M:%S')
                except ValueError as e:
                    db_logger.error("Invalid date format: %s", e)
                    return False

            db_logger.info("Updating match %d: %s vs %s, Date: %s, Type: %s",
                           match_id, team_a, team_b, match_date.strftime('%Y-%m-%d %I:%M %p'), match_name)

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    UPDATE matches
                    SET team_a = ?, team_b = ?, match_date = ?, match_name = ?
                    WHERE match_id = ?
                """, (team_a, team_b, match_date, match_name, match_id))
                conn.commit()
                db_logger.info("Match %d updated successfully", match_id)
                return True

        except sqlite3.Error as e:
            db_logger.error("Failed to update match: %s", e, exc_info=True)
            return False
        except Exception as e:
            db_logger.error("Error updating match: %s", e, exc_info=True)
            return False

    def get_user_stats(self, guild_id: int, user_id: int) -> dict:
        """Get user's pick'em statistics"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                WITH user_picks AS (
                    SELECT
                        p.pick_id,
                        p.is_correct,
                        m.winner IS NOT NULL as is_completed
                    FROM picks p
                    JOIN matches m ON p.match_id = m.match_id
                    WHERE p.user_id = ? AND p.guild_id = ?
                )
                SELECT
                    COUNT(*) as total_picks,
                    SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed_picks,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_picks
                FROM user_picks
            """, (user_id, guild_id))

            result = c.fetchone()
            total_picks = result[0] or 0
            completed_picks = result[1] or 0
            correct_picks = result[2] or 0

            # Calculate accuracy based only on completed matches
            accuracy = correct_picks / completed_picks if completed_picks > 0 else 0

            return {
                "total_picks": total_picks,
                "completed_picks": completed_picks,
                "correct_picks": correct_picks,
                "accuracy": accuracy
            }

    def get_leaderboard(self, guild_id: int, limit: int = 10) -> list:
        """Get top users by correct picks"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT
                    p.user_id,
                    COUNT(*) as completed_picks,
                    SUM(CASE WHEN p.is_correct = 1 THEN 1 ELSE 0 END) as correct_picks
                FROM picks p
                JOIN matches m ON p.match_id = m.match_id
                WHERE p.guild_id = ? AND m.winner IS NOT NULL
                GROUP BY p.user_id
                ORDER BY correct_picks DESC, completed_picks ASC
                LIMIT ?
            """, (guild_id, limit))
            return c.fetchall()

    def get_leaderboard_by_timeframe(self, guild_id: int, timeframe: str = 'all', limit: int = 10) -> list:
        """Get top users by correct picks or percentage within specified timeframe"""
        db_logger.debug("Fetching leaderboard for guild %d, timeframe: %s", guild_id, timeframe)
        try:
            # Base query for all timeframes
            base_query = """
                SELECT
                    p.user_id,
                    COUNT(*) as completed_picks,
                    SUM(CASE WHEN p.is_correct = 1 THEN 1 ELSE 0 END) as correct_picks,
                    CAST(SUM(CASE WHEN p.is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) /
                    CAST(COUNT(*) AS FLOAT) as accuracy
                FROM picks p
                JOIN matches m ON p.match_id = m.match_id
                WHERE p.guild_id = ?
                AND m.winner IS NOT NULL
            """

            # Add timeframe condition
            if timeframe == 'daily':
                base_query += " AND date(m.match_date) = date('now', 'localtime')"
            elif timeframe == 'weekly':
                base_query += " AND m.match_date >= datetime('now', '-7 days')"

            # Complete the query
            query = base_query + """
                GROUP BY p.user_id
                ORDER BY correct_picks DESC, completed_picks ASC
                LIMIT ?
            """

            # Execute query with parameters
            self._cursor.execute(query, (guild_id, limit))
            result = self._cursor.fetchall()
            db_logger.debug("Retrieved %d leaderboard entries", len(result))
            return result

        except sqlite3.Error as e:
            db_logger.error("Failed to get leaderboard: %s", e, exc_info=True)
            return []

    def get_total_users(self, guild_id: int):
        """Get total number of users"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("SELECT COUNT(DISTINCT user_id) FROM picks WHERE guild_id = ?", (guild_id,)).fetchone()[0]

    def get_active_picks_count(self, guild_id: int):
        """Get number of active picks"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("SELECT COUNT(*) FROM picks WHERE is_correct IS NULL AND guild_id = ?", (guild_id,)).fetchone()[0]

    def get_total_matches(self, guild_id: int):
        """Get total number of matches"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

    def get_user_activity(self, guild_id: int):
        """Get recent user activity"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("""
                SELECT
                    user_id as username,
                    MAX(created_at) as last_active,
                    COUNT(*) as total_picks,
                    ROUND(AVG(CASE WHEN is_correct = 1 THEN 100 ELSE 0 END), 2) as accuracy
                FROM picks
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY last_active DESC
                LIMIT 10
            """, (guild_id,)).fetchall()

    def get_all_matches(self):
        """Get all matches ordered by date with league info"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("""
                SELECT
                    m.match_id,
                    m.team_a,
                    m.team_b,
                    m.winner,
                    m.match_date,
                    m.created_at,
                    COALESCE(l.name, 'Unknown League') as league_name,
                    COALESCE(l.region, 'Global') as league_region,
                    m.match_name
                FROM matches m
                LEFT JOIN leagues l ON m.league_id = l.league_id
                ORDER BY m.match_date DESC
            """).fetchall()

    def get_active_matches(self):
        """Get all active matches that are open for picks - globally, including league info"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("""
                SELECT
                    m.match_id,
                    m.team_a,
                    m.team_b,
                    m.match_date,
                    COALESCE(l.name, 'Unknown League') as league_name,
                    COALESCE(l.region, 'Global') as league_region,
                    m.match_name
                FROM matches m
                LEFT JOIN leagues l ON m.league_id = l.league_id
                WHERE m.winner IS NULL
                AND (m.is_active = 1 OR m.is_active IS NULL)
                AND datetime(m.match_date) > datetime('now', 'localtime')
                ORDER BY m.match_date ASC
            """).fetchall()

    def close_match(self, match_id: int) -> bool:
        """Close a match for picks"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    UPDATE matches
                    SET is_active = 0
                    WHERE match_id = ?
                """, (match_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logging.error("Database error: %s", e)
            return False

    def open_match(self, match_id: int) -> bool:
        """Re-open a match for picks"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                        UPDATE matches
                        SET is_active = 1
                        WHERE match_id = ?
                        """, (match_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logging.error("Database error: %s", e)
            return False

    def get_global_stats(self) -> dict:
        """Get global statistics for the dashboard"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()

            # Get total matches
            total_matches = c.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

            # Get total users across all guilds
            total_users = c.execute("SELECT COUNT(DISTINCT user_id) FROM picks").fetchone()[0]

            # Get total picks across all guilds
            total_picks = c.execute("SELECT COUNT(*) FROM picks").fetchone()[0]

            # Get completed matches and correct picks
            c.execute("""
                SELECT
                    COUNT(DISTINCT m.match_id) as completed_matches,
                    COUNT(p.pick_id) as total_picks,
                    SUM(CASE WHEN p.is_correct = 1 THEN 1 ELSE 0 END) as correct_picks
                FROM matches m
                LEFT JOIN picks p ON m.match_id = p.match_id
                WHERE m.winner IS NOT NULL
            """)
            completed_stats = c.fetchone()

            return {
                "total_matches": total_matches,
                "total_users": total_users,
                "total_picks": total_picks,
                "completed_matches": completed_stats[0],
                "completed_picks": completed_stats[1] or 0,
                "correct_picks": completed_stats[2] or 0,
                "global_accuracy": (completed_stats[2] or 0) / completed_stats[1] if completed_stats[1] else 0
            }

    def get_guild_list(self) -> list:
        """Get list of all guilds with picks"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("""
                SELECT DISTINCT guild_id, COUNT(*) as pick_count
                FROM picks
                GROUP BY guild_id
                ORDER BY pick_count DESC
            """).fetchall()

    def get_upcoming_matches(self, hours: int = 36) -> list:
        """Get matches within the next specified hours that are open for picks"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            return c.execute("""
                SELECT
                    m.match_id,
                    m.team_a,
                    m.team_b,
                    m.match_date,
                    m.is_active,
                    COALESCE(l.name, 'Unknown League') as league_name,
                    COALESCE(l.region, 'Global') as league_region,
                    m.match_name
                FROM matches m
                LEFT JOIN leagues l ON m.league_id = l.league_id
                WHERE m.winner IS NULL
                AND (m.is_active = 1 OR m.is_active IS NULL)
                AND datetime(m.match_date) > datetime('now', 'localtime')
                AND datetime(m.match_date) <= datetime('now', 'localtime', ?||' hours')
                ORDER BY m.match_date ASC
            """, (str(hours),)).fetchall()

    def get_active_picks(self, guild_id: int, user_id: int) -> list:
        """Get all active picks for a user in a guild"""
        query = """
            SELECT
                m.match_id,
                m.team_a,
                m.team_b,
                m.match_date,
                p.pick,
                COALESCE(l.name, 'Unknown League') as league_name,
                COALESCE(l.region, 'Global') as league_region,
                m.match_name
            FROM matches m
            JOIN picks p ON m.match_id = p.match_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE p.guild_id = ?
            AND p.user_id = ?
            AND m.winner IS NULL
            AND datetime(m.match_date) > datetime('now', 'localtime')
            ORDER BY m.match_date ASC
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(query, (guild_id, user_id))
                return c.fetchall()
        except Exception as e:
            logging.error("Error getting active picks: %s", e)
            return []

    def get_match_details(self, match_id: int) -> dict:
        """Get detailed information about a specific match"""
        db_logger.debug("Fetching details for match %d", match_id)
        query = """
            SELECT
                m.match_id,
                m.team_a,
                m.team_b,
                m.match_date,
                m.is_active,
                m.match_name,
                COALESCE(l.name, 'Unknown League') as league_name,
                COALESCE(l.region, 'Global') as league_region
            FROM matches m
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = ?
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                result = c.execute(query, (match_id,)).fetchone()
                if result:
                    db_logger.debug("Match %d details retrieved successfully", match_id)
                    return {
                        'match_id': result[0],
                        'team_a': result[1],
                        'team_b': result[2],
                        'match_date': result[3],
                        'is_active': result[4],
                        'match_name': result[5],
                        'league_name': result[6],
                        'league_region': result[7]
                    }
                db_logger.warning("No match found with ID %d", match_id)
                return None
        except sqlite3.Error as e:
            logging.error("Database error: %s", e)
            db_logger.error("Failed to get match details: %s", e, exc_info=True)
            return None

    def get_user_pick(self, guild_id: int, user_id: int, match_id: int) -> str:
        """Get a user's pick for a specific match"""
        try:
            # Use class-level connection instead of creating new one
            self._cursor.execute("""
                SELECT pick FROM picks
                WHERE guild_id = ? AND user_id = ? AND match_id = ?
            """, (guild_id, user_id, match_id))
            result = self._cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            db_logger.error("Error getting user pick: %s", e)
            raise

    def get_ongoing_matches(self):
        """Get matches that are currently in progress (started but no winner)"""
        try:
            current_time = datetime.now()
            query = """
                SELECT * FROM matches
                WHERE match_date <= ?
                AND winner IS NULL
                ORDER BY match_date ASC
            """
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(query, (current_time,))
                return c.fetchall()
        except Exception as e:
            logging.error("Error getting ongoing matches: %s", e)
            return []

    def __del__(self):
        """Cleanup when database object is destroyed"""
        try:
            if hasattr(self, '_cursor') and self._cursor:
                self._cursor.close()
            if hasattr(self, '_conn') and self._conn:
                self._conn.close()
            db_logger.info("Database connection closed")
        except Exception as e:
            db_logger.error("Error closing database connection: %s", e)

# Add a function to handle database errors
def handle_db_error(func):
    """Decorator to handle database errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            db_logger.error("Database error in %s: %s", func.__name__, e, exc_info=True)
            return None
    return wrapper
