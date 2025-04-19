from src.database.database import Database
from src.utils.logging_config import configure_logging
from src.database.models.user import User
from src.database.models.match import Match
from typing import Optional, List, Literal
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
        log.debug("Validating user and match existence for pick creation")

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
        """.strip()
        current_time = datetime.now(timezone.utc)
        
        try:
            pick_id = await db.execute(query, (user_id, match_id, pick_selection, current_time))
            if pick_id is not None:
                log.info(f"Pick successfully created with ID {pick_id}")
                return Pick(pick_id=pick_id, user_id=user_id, match_id=match_id,
                          pick_selection=pick_selection, pick_timestamp=current_time)

            # This case indicates db.execute returned None instead of an ID
            error_msg = f"Failed to create pick for user {user_id} on match {match_id} - no ID returned."
            log.error(error_msg)
            raise RuntimeError(error_msg)

        except RuntimeError:
            raise  # Re-raise RuntimeError without modification
        except Exception as e:
            error_msg = f"Database error creating pick for user {user_id} on match {match_id}: {str(e)}"
            log.error(error_msg)
            raise RuntimeError(f"Database error creating pick: {str(e)}") from e

    @staticmethod
    async def get_by_id(db: Database, pick_id: int) -> Optional['Pick']:
        """
        Retrieve a pick by its ID.

        Args:
            db (Database): Database instance to use for the query.
            pick_id (int): The ID of the pick to retrieve.

        Returns:
            Pick: A Pick instance if found, None otherwise.

        Raises:
            ValueError: If pick_id is invalid (<= 0).
            RuntimeError: If there's an error during database retrieval.
        """
        log.debug("Validating pick_id for retrieval")

        if pick_id <= 0:
            log.error("Invalid pick_id provided.")
            raise ValueError("Invalid pick_id provided.")

        log.info(f"Retrieving pick with ID: {pick_id}")
        query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE pick_id = ?
        """
        try:
            row = await db.fetch_one(query, (pick_id,))
            if row:
                log.info(f"Pick with ID {pick_id} retrieved successfully.")
                return Pick(**dict(row))  # Return the Pick instance here

            log.warning(f"No pick found with ID {pick_id}")
            return None
        except Exception as e:
            log.error(f"Error retrieving pick with ID {pick_id}: {str(e)}")
            raise RuntimeError(f"Error retrieving pick: {str(e)}") from e

    @staticmethod
    async def get_by_user_id(db: Database, user_id: int) -> List['Pick']:
        """
        Retrieve all picks made by a user.

        Args:
            db (Database): Database instance to use for the query.
            user_id (int): The ID of the user whose picks to retrieve.

        Returns:
            List[Pick]: A list of Pick instances if found, empty list otherwise.

        Raises:
            ValueError: If user_id is invalid (<= 0).
            RuntimeError: If there's an error during database retrieval.
        """
        log.debug("Validating user_id for pick retrieval")

        if user_id <= 0:
            log.error("Invalid user_id provided.")
            raise ValueError("Invalid user_id provided.")

        # Validate user_id existence
        user = await User.get_by_id(db, user_id)
        if not user:
            log.error(f"User with ID {user_id} does not exist.")
            raise ValueError(f"User with ID {user_id} does not exist.")

        log.info(f"Retrieving picks for user with ID: {user_id}")
        query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ?
        """
        try:
            rows = await db.fetch_many(query, (user_id,))
            if rows:
                log.info(f"Picks for user {user_id} retrieved successfully.")
                return [Pick(**dict(row)) for row in rows]  # Return a list of Pick instances

            log.warning(f"No picks found for user with ID {user_id}")
            return []
        except Exception as e:
            log.error(f"Error retrieving picks for user with ID {user_id}: {str(e)}")
            raise RuntimeError(f"Error retrieving picks: {str(e)}") from e

    @staticmethod
    async def get_by_match_id(db: Database, match_id: int) -> List['Pick']:
        """
        Retrieve all picks made for a specific match.

        Args:
            db (Database): Database instance to use for the query.
            match_id (int): The ID of the match whose picks to retrieve.

        Returns:
            List[Pick]: A list of Pick instances if found, empty list otherwise.

        Raises:
            ValueError: If match_id is invalid (<= 0).
            RuntimeError: If there's an error during database retrieval.
        """
        log.debug("Validating match_id for pick retrieval")

        if match_id <= 0:
            log.error("Invalid match_id provided.")
            raise ValueError("Invalid match_id provided.")

        # Validate match_id existence
        match = await Match.get_by_id(db, match_id)
        if not match:
            log.error(f"Match with ID {match_id} does not exist.")
            raise ValueError(f"Match with ID {match_id} does not exist.")

        log.info(f"Retrieving picks for match with ID: {match_id}")
        query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE match_id = ?
        """
        try:
            rows = await db.fetch_many(query, (match_id,))
            if rows:
                log.info(f"Picks for match {match_id} retrieved successfully.")
                return [Pick(**dict(row)) for row in rows]  # Return a list of Pick instances

            log.warning(f"No picks found for match with ID {match_id}")
            return []
        except Exception as e:
            log.error(f"Error retrieving picks for match with ID {match_id}: {str(e)}")
            raise RuntimeError(f"Error retrieving picks: {str(e)}") from e

    @staticmethod
    async def get_by_user_and_match(db: Database, user_id: int, match_id: int) -> Optional['Pick']:
        """
        Retrieve a pick by user ID and match ID.

        Args:
            db (Database): Database instance to use for the query.
            user_id (int): The ID of the user whose pick to retrieve.
            match_id (int): The ID of the match for which the pick is made.

        Returns:
            Pick: A Pick instance if found, None otherwise.

        Raises:
            ValueError: If user_id or match_id are invalid (<= 0) or, if the user or match does not exist.
            RuntimeError: If there's an error during database retrieval.
        """
        log.debug("Validating user_id and match_id for pick retrieval")

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

        log.info(f"Retrieving pick for user {user_id} on match {match_id}")
        query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ? AND match_id = ?
        """
        try:
            row = await db.fetch_one(query, (user_id, match_id))
            if row:
                log.info(f"Pick for user {user_id} on match {match_id} retrieved successfully.")
                return Pick(**dict(row))  # Return the Pick instance here

            log.warning(f"No pick found for user {user_id} on match {match_id}")
            return None
        except Exception as e:
            log.error(f"Error retrieving pick for user {user_id} on match {match_id}: {str(e)}")
            raise RuntimeError(f"Error retrieving pick: {str(e)}") from e

    @staticmethod
    async def get_all(db: Database, limit: int = 100, offset: int = 0) -> List['Pick']:
        """
        Retrieve all picks from the database.

        Args:
            db (Database): Database instance to use for the query.
            limit (int): Maximum number of picks to retrieve.
            offset (int): Number of picks to skip before starting to collect the result set.

        Returns:
            List[Pick]: A list of Pick instances if found, empty list otherwise.

        Raises:
            RuntimeError: If there's an error during database retrieval.
        """
        log.info(f"Retrieving all picks with limit {limit} and offset {offset}")
        query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            LIMIT ? OFFSET ?
        """
        try:
            rows = await db.fetch_many(query, (limit, offset))
            if rows:
                log.info("All picks retrieved successfully.")
                return [Pick(**dict(row)) for row in rows]  # Return a list of Pick instances

            log.warning("No picks found in the database")
            return []
        except Exception as e:
            log.error(f"Error retrieving all picks: {str(e)}")
            raise RuntimeError(f"Error retrieving all picks: {str(e)}") from e

    @staticmethod
    async def update(update_mode: Literal['pick', 'result'], db: Database, pick_id: int, is_correct: Optional[bool] = None,
                     points_earned: Optional[int] = None, pick_selection: Optional[str] = None,
                     pick_timestamp: Optional[datetime] = None) -> Optional['Pick']:
        """
        Update a pick in the database.

        Args:
            update_mode (str): Mode of update to perform, e.g., 'pick' and 'result'.
            db (Database): Database instance to use for the query.
            pick_id (int): The ID of the pick to update.
            is_correct (Optional[bool]): Indicates if the prediction was correct.
            points_earned (Optional[int]): Points awarded for a correct prediction.
            pick_selection (Optional[str]): The selection made by the user.
            pick_timestamp (Optional[datetime]): The timestamp of the pick.

        Returns:
            Pick: The updated Pick instance if successful, None otherwise.

        Raises:
            ValueError: If pick_id is invalid (<= 0).
            RuntimeError: If there's an error during database update or retrieval.
        """
        log.debug("Validating pick_id for update")

        if pick_id <= 0:
            log.error("Invalid pick_id provided.")
            raise ValueError("Invalid pick_id provided.")

        # Validate pick existence
        existing_pick = await Pick.get_by_id(db, pick_id)
        if not existing_pick:
            log.error(f"Pick with ID {pick_id} does not exist.")
            raise ValueError(f"Pick with ID {pick_id} does not exist.")

        log.info(f"{update_mode.capitalize()} update for pick with ID: {pick_id}")

        if update_mode == 'pick':
            if pick_selection is None or pick_timestamp is None:
                log.error("pick_selection and pick_timestamp must be provided for 'pick' update mode.")
                raise ValueError("pick_selection and pick_timestamp must be provided for 'pick' update mode.")
            query = """
                UPDATE Picks
                SET pick_selection = ?, pick_timestamp = ?
                WHERE pick_id = ?
            """
            try:
                await db.execute(query, (pick_selection, pick_timestamp, pick_id))
                log.info(f"Pick with ID {pick_id} updated successfully.")
                return await Pick.get_by_id(db, pick_id)  # Return the updated Pick instance

            except Exception as e:
                log.error(f"Error updating pick with ID {pick_id}: {str(e)}")
                raise RuntimeError(f"Error updating pick: {str(e)}") from e
        elif update_mode == 'result':
            query = """
                UPDATE Picks
                SET is_correct = ?, points_earned = ?
                WHERE pick_id = ?
            """
            try:
                await db.execute(query, (is_correct, points_earned, pick_id))
                log.info(f"Result for pick with ID {pick_id} updated successfully.")
                return await Pick.get_by_id(db, pick_id)  # Return the updated Pick instance

            except Exception as e:
                log.error(f"Error updating result for pick with ID {pick_id}: {str(e)}")
                raise RuntimeError(f"Error updating result: {str(e)}") from e
        else:
            log.error(f"Invalid update mode: {update_mode}. Must be 'pick' or 'result'.")
            raise ValueError(f"Invalid update mode: {update_mode}. Must be 'pick' or 'result'.")
