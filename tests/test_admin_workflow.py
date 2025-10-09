"""
Integration tests for admin workflow: create contest and upload matches.
"""

from datetime import datetime, timezone
from sqlmodel import SQLModel, Session, create_engine

from src import crud
from src.csv_utils import parse_match_csv


def test_create_contest_and_upload_matches_workflow(tmp_path):
    """
    Test the complete workflow:
    1. Create a contest
    2. Parse CSV with matches
    3. Create matches in the database
    """
    # Set up test database
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Step 1: Create a contest
        contest = crud.create_contest(
            session,
            name="VCT 2025 Spring Split",
            start_date=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
        )

        assert contest.id is not None
        assert contest.name == "VCT 2025 Spring Split"

        # Step 2: Parse CSV with matches
        csv_content = """scheduled_time,team1,team2,external_id
2025-01-15T14:00:00Z,Team Liquid,Cloud9,vlr-match-001
2025-01-15T16:30:00Z,Sentinels,100 Thieves,vlr-match-002
2025-01-16T14:00:00Z,LOUD,NRG Esports,vlr-match-003
"""
        valid_rows, errors = parse_match_csv(csv_content)

        assert len(errors) == 0
        assert len(valid_rows) == 3

        # Step 3: Create matches in the database
        created_matches = []
        for row in valid_rows:
            match = crud.create_match(
                session,
                contest_id=contest.id,
                team1=row["team1"],
                team2=row["team2"],
                scheduled_time=row["scheduled_time"]
            )
            created_matches.append(match)

        assert len(created_matches) == 3

        # Step 4: Verify matches are in the database
        matches = crud.list_matches_for_contest(session, contest.id)
        assert len(matches) == 3

        # Verify match details
        match_teams = [(m.team1, m.team2) for m in matches]
        assert ("Team Liquid", "Cloud9") in match_teams
        assert ("Sentinels", "100 Thieves") in match_teams
        assert ("LOUD", "NRG Esports") in match_teams


def test_csv_validation_prevents_bad_data(tmp_path):
    """
    Test that CSV validation prevents bad data from being imported.
    """
    # Set up test database
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Create a contest
        contest = crud.create_contest(
            session,
            name="Test Contest",
            start_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        )

        # CSV with errors
        csv_content = """scheduled_time,team1,team2
invalid-date,Team A,Team B
2025-01-15T14:00:00Z,,Team C
2025-01-16T14:00:00Z,Team D,
"""
        valid_rows, errors = parse_match_csv(csv_content)

        # All rows should have errors
        assert len(valid_rows) == 0
        assert len(errors) == 3

        # Verify no matches were created
        matches = crud.list_matches_for_contest(session, contest.id)
        assert len(matches) == 0


def test_partial_csv_import(tmp_path):
    """
    Test that valid rows are parsed even if some rows have errors.
    """
    csv_content = """scheduled_time,team1,team2
2025-01-15T14:00:00Z,Team A,Team B
invalid-date,Team C,Team D
2025-01-16T14:00:00Z,Team E,Team F
"""
    valid_rows, errors = parse_match_csv(csv_content)

    # Only 2 valid rows
    assert len(valid_rows) == 2
    assert len(errors) == 1

    # Check valid rows
    assert valid_rows[0]["team1"] == "Team A"
    assert valid_rows[1]["team1"] == "Team E"
