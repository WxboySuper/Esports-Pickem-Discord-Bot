from datetime import datetime, timezone

from src.csv_utils import parse_match_csv


def test_parse_match_csv_valid():
    """Test parsing valid CSV with required fields."""
    csv_content = """scheduled_time,team1,team2
2025-01-15T14:00:00Z,Team A,Team B
2025-01-16T15:30:00Z,Team C,Team D
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(errors) == 0
    assert len(valid_rows) == 2

    assert valid_rows[0]["team1"] == "Team A"
    assert valid_rows[0]["team2"] == "Team B"
    assert valid_rows[0]["scheduled_time"] == datetime(
        2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc
    )

    assert valid_rows[1]["team1"] == "Team C"
    assert valid_rows[1]["team2"] == "Team D"


def test_parse_match_csv_with_external_id():
    """Test parsing CSV with optional external_id field."""
    csv_content = """scheduled_time,team1,team2,external_id
2025-01-15T14:00:00Z,Team A,Team B,match-001
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(errors) == 0
    assert len(valid_rows) == 1
    assert valid_rows[0]["external_id"] == "match-001"


def test_parse_match_csv_missing_headers():
    """Test parsing CSV with missing required headers."""
    csv_content = """scheduled_time,team1
2025-01-15T14:00:00Z,Team A
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(valid_rows) == 0
    assert len(errors) == 1
    assert "missing required headers" in errors[0].lower()
    assert "team2" in errors[0]


def test_parse_match_csv_empty_fields():
    """Test parsing CSV with empty required fields."""
    csv_content = """scheduled_time,team1,team2
2025-01-15T14:00:00Z,,Team B
,Team A,Team B
2025-01-15T14:00:00Z,Team A,
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(valid_rows) == 0
    assert len(errors) == 3
    assert any("team1 is empty" in err for err in errors)
    assert any("scheduled_time is empty" in err for err in errors)
    assert any("team2 is empty" in err for err in errors)


def test_parse_match_csv_invalid_datetime():
    """Test parsing CSV with invalid datetime format."""
    csv_content = """scheduled_time,team1,team2
not-a-date,Team A,Team B
2025-13-45T25:99:99Z,Team C,Team D
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(valid_rows) == 0
    assert len(errors) == 2
    assert all("Invalid datetime format" in err for err in errors)


def test_parse_match_csv_mixed_valid_invalid():
    """Test parsing CSV with mix of valid and invalid rows."""
    csv_content = """scheduled_time,team1,team2
2025-01-15T14:00:00Z,Team A,Team B
invalid-date,Team C,Team D
2025-01-16T15:00:00Z,Team E,Team F
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(valid_rows) == 2
    assert len(errors) == 1
    assert "Row 3" in errors[0]


def test_parse_match_csv_empty_file():
    """Test parsing empty CSV content."""
    csv_content = ""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(valid_rows) == 0
    assert len(errors) == 1
    assert "empty" in errors[0].lower()


def test_parse_match_csv_only_header():
    """Test parsing CSV with only header row."""
    csv_content = """scheduled_time,team1,team2
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(valid_rows) == 0
    assert len(errors) == 0  # Valid CSV, just no data rows


def test_parse_match_csv_whitespace_handling():
    """Test that whitespace is properly trimmed."""
    csv_content = """scheduled_time,team1,team2
 2025-01-15T14:00:00Z , Team A , Team B
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(errors) == 0
    assert len(valid_rows) == 1
    assert valid_rows[0]["team1"] == "Team A"
    assert valid_rows[0]["team2"] == "Team B"


def test_parse_match_csv_iso_format_without_z():
    """Test parsing ISO format datetime without Z suffix."""
    csv_content = """scheduled_time,team1,team2
2025-01-15T14:00:00+00:00,Team A,Team B
"""
    valid_rows, errors = parse_match_csv(csv_content)

    assert len(errors) == 0
    assert len(valid_rows) == 1
    assert valid_rows[0]["scheduled_time"] == datetime(
        2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc
    )
