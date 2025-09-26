import pytz
from datetime import datetime, timedelta

# --- Constants ---
TIMEZONE = pytz.timezone('Asia/Bangkok')

def get_current_time() -> datetime:
    """Returns the current time in the specified timezone."""
    return datetime.now(TIMEZONE)

def get_shift_date() -> datetime:
    """
    Determines the correct "shift date" for logging.
    If it's before 6 AM, it belongs to the previous day's shift.
    """
    now = get_current_time()
    if now.hour < 6:
        return now - timedelta(days=1)
    return now

def format_duration(seconds: float) -> str:
    """Formats a duration in seconds into HH:MM:SS format."""
    if seconds < 0:
        seconds = 0
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

# Alias for backward compatibility if needed elsewhere
format_seconds = format_duration

