import csv
import os
from datetime import datetime
from telegram import User

from utils.time_utils import get_current_time, get_shift_date

# --- Constants ---
LOG_FILE = 'work_tracker_log.csv'
LOG_HEADER = ['timestamp_utc', 'user_id', 'username', 'event', 'details', 'shift_date']

def log_activity(user: User, event: str, details: str):
    """Logs an activity to the CSV file."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(LOG_HEADER)

    try:
        now = get_current_time()
        # FIX: The get_shift_date() function no longer requires an argument.
        shift_date_str = get_shift_date().strftime('%Y-%m-%d')
        
        log_entry = [
            now.isoformat(),
            user.id,
            user.username or user.first_name,
            event,
            details,
            shift_date_str
        ]
        
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(log_entry)
            
    except Exception as e:
        print(f"Error writing to log file: {e}")

