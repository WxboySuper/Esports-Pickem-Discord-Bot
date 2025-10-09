from unittest.mock import patch

from src.admin_utils import is_admin


def test_is_admin_true():
    """Test that is_admin returns True for valid admin IDs."""
    with patch('src.admin_utils.ADMIN_IDS', [123, 456, 789]):
        assert is_admin(123) is True
        assert is_admin(456) is True
        assert is_admin(789) is True


def test_is_admin_false():
    """Test that is_admin returns False for non-admin IDs."""
    with patch('src.admin_utils.ADMIN_IDS', [123, 456, 789]):
        assert is_admin(999) is False
        assert is_admin(0) is False
        assert is_admin(111) is False


def test_is_admin_empty_list():
    """Test that is_admin returns False when no admins configured."""
    with patch('src.admin_utils.ADMIN_IDS', []):
        assert is_admin(123) is False
