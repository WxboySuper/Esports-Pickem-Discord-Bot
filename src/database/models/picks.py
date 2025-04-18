from src.database.database import Database
from src.utils.logging_config import configure_logging
from typing import Optional
from datetime import datetime

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