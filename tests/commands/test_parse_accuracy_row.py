from src.commands.leaderboard import _parse_accuracy_row
from src.models import User

def test_parse_accuracy_row_basic():
    user = User(id=1, username="test")
    row = (user, 75.0, 3, 4)
    result = _parse_accuracy_row(row)
    assert result == (user, 75.0, 3, 4)

def test_parse_accuracy_row_legacy_fraction():
    user = User(id=1, username="test")
    # accuracy is 0.75 (3/4), which is a legacy fraction
    row = (user, 0.75, 3, 4)
    result = _parse_accuracy_row(row)
    # should be converted to 75.0
    assert result == (user, 75.0, 3, 4)

def test_parse_accuracy_row_not_legacy_if_matches_percentage():
    user = User(id=1, username="test")
    # accuracy is already 0.75% (very low but possible)
    # If 100 * (3/400) == 0.75, and accuracy is 0.75, it shouldn't be multiplied again
    # Wait, the logic is: if it matches fractional (3/4 = 0.75) 
    # AND is significantly different from percentage (300/4 = 75.0).
    # 0.75 is different from 75.0, so it IS legacy.
    row = (user, 0.75, 3, 4)
    result = _parse_accuracy_row(row)
    assert result[1] == 75.0

def test_parse_accuracy_row_clamping():
    user = User(id=1, username="test")
    assert _parse_accuracy_row((user, -10.0, 0, 10))[1] == 0.0
    assert _parse_accuracy_row((user, 110.0, 11, 10))[1] == 100.0

def test_parse_accuracy_row_missing_elements():
    user = User(id=1, username="test")
    assert _parse_accuracy_row((user,)) == (user, 0.0, 0, 0)
    assert _parse_accuracy_row((user, 50.0)) == (user, 50.0, 0, 0)

def test_parse_accuracy_row_negative_correct():
    user = User(id=1, username="test")
    assert _parse_accuracy_row((user, 50.0, -1, 10)) == (user, 50.0, 0, 10)
