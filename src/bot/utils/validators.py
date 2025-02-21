def validate_user_id(user_id: str) -> int:
    """Validate and convert user ID to integer"""
    if not user_id:
        raise ValueError("Owner user ID not set in environment variables")
    try:
        return int(user_id)
    except ValueError:
        raise ValueError("Invalid owner user ID. Must be an integer") from None
