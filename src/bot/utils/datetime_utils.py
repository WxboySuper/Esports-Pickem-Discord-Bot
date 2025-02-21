from datetime import datetime

def get_discord_timestamp(dt: datetime, style: str = 'R') -> str:
    """Convert datetime to Discord timestamp"""
    return f"<t:{int(dt.timestamp())}:{style}>"

def parse_datetime(date_str: str, time_str: str) -> datetime:
    """Convert date and AM/PM time to datetime object"""
    try:
        time_obj = datetime.strptime(time_str.strip(), "%I:%M %p").time()
        date_obj = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        return datetime.combine(date_obj, time_obj)
    except ValueError as date_error:
        raise ValueError("Invalid date/time format. Use: YYYY-MM-DD for date and HH:MM AM/PM for time") from date_error

def ensure_datetime(date_value) -> datetime:
    """Convert string or datetime to datetime object"""
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
        except ValueError as val_error:
            raise ValueError(f"Invalid datetime format: {date_value}") from val_error
    elif isinstance(date_value, datetime):
        return date_value
    else:
        raise ValueError(f"Cannot convert {type(date_value)} to datetime")
