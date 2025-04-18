from src.database.database import Database
from src.utils.logging_config import configure_logging
from src.database.models.user import User
from src.database.models.match import Match
from typing import Optional
from datetime import timezone, datetime

log = configure_logging()


class Pick:
    """
    Handles operations related to a user pick in the database.

    This class provides methods to manage user predictions for esports matches,
    interacting with the 'Pick' table. It allows creating, retrieving,
    updating, and potentially deleting pick records.

    Attributes:
        db (Database): An instance of the Database class used for database operations.

    Database Table ('Picks'):
        - pick_id (Primary Key): Unique identifier for each pick.
        - user_id (Foreign Key): References the User table (User.user_id).
        - match_id (Foreign Key): References the Matches table (Matches.match_id).
        - pick_selection: User's prediction (e.g., team1_id, team2_id).
        - pick_timestamp: Timestamp indicating when the pick was made or last updated.
        - is_correct: Boolean indicating if the prediction was correct (Null until match is resolved).
        - points_earned: Points awarded for a correct prediction (Null until resolved).
    """

    def __init__(self, pick_id: Optional[int] = None, user_id: Optional[int] = None, match_id: Optional[int] = None,
                 pick_selection: Optional[str] = None, pick_timestamp: Optional[datetime] = None,
                 is_correct: Optional[bool] = None, points_earned: Optional[int] = None):
        self.pick_id = pick_id
        self.user_id = user_id
        self.match_id = match_id
        self.pick_selection = pick_selection
        self.pick_timestamp = pick_timestamp if isinstance(pick_timestamp, datetime) else None
        self.is_correct = is_correct
        self.points_earned = points_earned
    
    @staticmethod
    async def create(db: Database, user_id: int, match_id: int, pick_selection: str) -> 'Pick':
        """
        Create a new pick in the database.

        Args:
            db (Database): Database instance to use for the query.
            user_id (int): The ID of the user making the pick.
            match_id (int): The ID of the match for which the pick is made.
            pick_selection (str): The user's prediction (e.g., team1_id, team2_id).

        Returns:
            Pick: A new Pick instance if creation was successful.

        Raises:
            ValueError: If user_id or match_id are invalid (<= 0).
            ValueError: If the specified user_id does not exist.
            ValueError: If the specified match_id does not exist.
            RuntimeError: If there's an error during database insertion or if the pick_id is not returned.
        """
        if user_id <= 0 or match_id <= 0:
            log.error("Invalid user_id or match_id provided.")
            raise ValueError("Invalid user_id or match_id provided.")

        # Validate User and Match existence
        user = await User.get_by_id(db, user_id)
        if not user:
            log.error(f"User with ID {user_id} does not exist.")
            raise ValueError(f"User with ID {user_id} does not exist.")

        match = await Match.get_by_id(db, match_id)
        if not match:
            log.error(f"Match with ID {match_id} does not exist.")
            raise ValueError(f"Match with ID {match_id} does not exist.")

        log.info(f"Creating pick for user {user_id} on match {match_id} with selection {pick_selection}")
        query = """
            INSERT INTO Picks (user_id, match_id, pick_selection, pick_timestamp)
            VALUES (?, ?, ?, ?)
        """
        current_time = datetime.now(timezone.utc)
        try:
            pick_id = await db.execute(query, (user_id, match_id, pick_selection, current_time))
            if pick_id is not None:
                log.info(f"Pick successfully created with ID {pick_id}")
                return Pick(pick_id=pick_id, user_id=user_id, match_id=match_id,
                            pick_selection=pick_selection, pick_timestamp=current_time)
            else:
                # This case might indicate an issue with db.execute returning a non-ID value on success
                log.error(f"Failed to create pick for user {user_id} on match {match_id} - no ID returned.")
                raise RuntimeError(f"Failed to create pick for user {user_id} on match {match_id} - no ID returned.")
        except Exception as e:
            log.error(f"Database error creating pick for user {user_id} on match {match_id}: {str(e)}")
            # Re-raise as a runtime error to be caught upstream
            raise RuntimeError(f"Database error creating pick: {str(e)}") from e