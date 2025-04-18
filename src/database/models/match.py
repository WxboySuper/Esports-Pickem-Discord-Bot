import json
from typing import Optional, List, Dict, Any
from src.database.database import Database
from src.utils.logging_config import configure_logging

log = configure_logging()


class Match:
    """
    Interface for match-related database operations.

    This model provides methods to create, retrieve, update, and delete
    match records in the database.
    """

    def __init__(self, match_id: Optional[int] = None, team1_id: Optional[int] = None, team1_name: Optional[str] = None,
                 team2_id: Optional[int] = None, team2_name: Optional[str] = None, region: Optional[str] = None,
                 tournament: Optional[str] = None, match_date: Optional[str] = None, match_time: Optional[str] = None,
                 result: Optional[str] = None, is_complete: bool = False, match_metadata: Optional[Dict[str, Any]] = None):
        self.match_id = match_id
        self.team1_id = team1_id
        self.team1_name = team1_name
        self.team2_id = team2_id
        self.team2_name = team2_name
        self.region = region
        self.tournament = tournament
        self.match_date = match_date  # Store as ISO format string or date object? Let's use string for now.
        self.match_time = match_time  # Store as ISO format string or time object? Let's use string for now.
        self.result = result  # e.g., 'team1', 'team2', 'draw'
        self.is_complete = is_complete
        self.match_metadata = match_metadata  # Store as JSON string in DB, dict here

    @staticmethod
    async def create(db: Database, team1_id: int, team1_name: str, team2_id: int, team2_name: str,
                     region: str, tournament: str, match_date: str, match_time: str,
                     match_metadata: Optional[Dict[str, Any]] = None) -> Optional['Match']:
        """Create a new match in the database."""
        log.info(f"Creating match: {team1_name} vs {team2_name} on {match_date}")
        query = """
            INSERT INTO matches (team1_id, team1_name, team2_id, team2_name, region, tournament, match_date, match_time, match_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """.strip()  # Strip leading/trailing whitespace
        # Convert metadata dict to JSON string for storage
        metadata_str = json.dumps(match_metadata) if match_metadata else None
        params = (team1_id, team1_name, team2_id, team2_name, region, tournament, match_date, match_time, metadata_str)
        try:
            match_id = await db.execute(query, params)
            if match_id:
                log.info(f"Match created successfully with ID {match_id}")
                # Return a new Match instance - need to handle potential date/time conversion if needed
                return Match(match_id=match_id, team1_id=team1_id, team1_name=team1_name, team2_id=team2_id,
                             team2_name=team2_name, region=region, tournament=tournament, match_date=match_date,
                             match_time=match_time, match_metadata=match_metadata)
            log.error("Failed to create match.")
            return None
        except Exception as e:
            log.error(f"Error creating match: {str(e)}")
            return None

    @staticmethod
    async def get_by_id(db: Database, match_id: int) -> Optional['Match']:
        """Retrieve a match by its ID."""
        if match_id <= 0:
            log.error("Invalid match_id provided.")
            return None

        log.info(f"Retrieving match with ID {match_id}")
        query = "SELECT * FROM matches WHERE match_id = ?"
        try:
            row = await db.fetch_one(query, (match_id,))
            if row:
                # Convert metadata JSON string back to dict
                if row.get('match_metadata'):
                    try:
                        row['match_metadata'] = json.loads(row['match_metadata'])
                    except json.JSONDecodeError:
                        log.warning(f"Failed to decode metadata for match {match_id}")
                        row['match_metadata'] = None  # Or handle differently
                return Match(**row)
            log.warning(f"No match found with ID {match_id}")
            return None
        except Exception as e:
            log.error(f"Error retrieving match with ID {match_id}: {str(e)}")
            return None

    @staticmethod
    async def get_upcoming(db: Database, limit: int = 100, offset: int = 0) -> List['Match']:
        """Retrieve upcoming (not complete) matches."""
        log.info(f"Retrieving upcoming matches with limit {limit} and offset {offset}")
        query = """
            SELECT * FROM matches
            WHERE is_complete = 0
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()  # Strip leading/trailing whitespace
        try:
            rows = await db.fetch_many(query, (limit, offset))
            matches = []
            for row in rows:
                # Convert metadata JSON string back to dict
                if row.get('match_metadata'):
                    try:
                        row['match_metadata'] = json.loads(row['match_metadata'])
                    except json.JSONDecodeError:
                        log.warning(f"Failed to decode metadata for match {row['match_id']}")
                        row['match_metadata'] = None
                matches.append(Match(**row))
            if not matches:
                log.info("No upcoming matches found.")
            return matches
        except Exception as e:
            log.error(f"Error retrieving upcoming matches: {str(e)}")
            return []

    @staticmethod
    async def update_result(db: Database, match_id: int, result: str, is_complete: bool = True) -> bool:
        """Update the result and completion status of a match."""
        if match_id <= 0:
            log.error("Invalid match_id provided for update.")
            return False

        # skipcq: W0511
        # TODO: Implement result validation after teams database is created

        log.info(f"Updating result for match ID {match_id} to {result}")
        query = "UPDATE matches SET result = ?, is_complete = ? WHERE match_id = ?"
        try:
            rows_affected = await db.execute(query, (result, is_complete, match_id))
            if rows_affected == 0 or rows_affected is None:
                log.warning(f"No rows affected. Match {match_id} may not exist or update failed.")
                return False
            log.info(f"Match {match_id} result updated successfully.")
            return True
        except Exception as e:
            log.error(f"Error updating result for match {match_id}: {str(e)}")
            return False

    @staticmethod
    async def delete_match(db: Database, match_id: int) -> bool:
        """Delete a match by its ID."""
        if match_id <= 0:
            log.error("Invalid match_id provided for deletion.")
            return False

        log.info(f"Deleting match with ID {match_id}")
        query = "DELETE FROM matches WHERE match_id = ?"
        try:
            rows_affected = await db.execute(query, (match_id,))
            if rows_affected == 0 or rows_affected is None:
                log.warning(f"No rows affected. Match {match_id} may not exist or deletion failed.")
                return False
            log.info(f"Match {match_id} deleted successfully.")
            return True
        except Exception as e:
            log.error(f"Error deleting match {match_id}: {str(e)}")
            return False

    @staticmethod
    async def get_by_day(db: Database, date: str) -> List['Match']:
        """Retrieve all matches scheduled for a specific date."""
        # Basic validation could be added here for date format if needed
        log.info(f"Retrieving matches for date {date}")
        query = "SELECT * FROM matches WHERE match_date = ? ORDER BY match_time"
        try:
            rows = await db.fetch_many(query, (date,))
            matches = []
            for row in rows:
                # Convert metadata JSON string back to dict
                if row.get('match_metadata'):
                    try:
                        row['match_metadata'] = json.loads(row['match_metadata'])
                    except json.JSONDecodeError:
                        log.warning(f"Failed to decode metadata for match {row['match_id']}")
                        row['match_metadata'] = None
                matches.append(Match(**row))
            if not matches:
                log.info(f"No matches found for date {date}.")
            return matches
        except Exception as e:
            log.error(f"Error retrieving matches for date {date}: {str(e)}")
            return []

    @staticmethod
    async def get_by_tournament(db: Database, tournament: str, limit: int = 100, offset: int = 0) -> List['Match']:
        """Retrieve matches belonging to a specific tournament."""
        if not tournament:
            log.error("Tournament name cannot be empty.")
            return []

        log.info(f"Retrieving matches for tournament '{tournament}' with limit {limit} and offset {offset}")
        query = """
            SELECT * FROM matches
            WHERE tournament = ?
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()
        try:
            rows = await db.fetch_many(query, (tournament, limit, offset))
            matches = []
            for row in rows:
                # Convert metadata JSON string back to dict
                if row.get('match_metadata'):
                    try:
                        row['match_metadata'] = json.loads(row['match_metadata'])
                    except json.JSONDecodeError:
                        log.warning(f"Failed to decode metadata for match {row['match_id']}")
                        row['match_metadata'] = None
                matches.append(Match(**row))
            if not matches:
                log.info(f"No matches found for tournament '{tournament}'.")
            return matches
        except Exception as e:
            log.error(f"Error retrieving matches for tournament '{tournament}': {str(e)}")
            return []
