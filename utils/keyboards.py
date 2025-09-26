from telegram import ReplyKeyboardMarkup

# --- Constants (ensure these match your handlers/breaks.py) ---
MAX_TOILET_BREAKS = 6
MAX_EAT_BREAKS = 1
MAX_REST_BREAKS = 1

# --- Keyboard Definitions ---

# Keyboard for when a user is on a break
on_break_keyboard = [['🏃 Back to Seat']]

# Keyboard for Yes/No confirmations
confirmation_keyboard = [['✅ Yes', '❌ No']]


def main_keyboard(user_data: dict) -> list:
    """
    Dynamically generates the main keyboard based on the user's current state.
    This function is written to be safe and avoid crashes.
    """
    # If user_data is missing or work hasn't started, show only the start button.
    if not user_data or not user_data.get('work_started'):
        return [['🚀 Start Work']]

    # If work has started, build the keyboard with available break options.
    keyboard_buttons = []
    
    # Safely get the number of breaks taken, defaulting to 0 if not found.
    toilet_breaks_taken = user_data.get('toilet_breaks_today', 0)
    if toilet_breaks_taken < MAX_TOILET_BREAKS:
        keyboard_buttons.append('🚽 Toilet')

    eat_breaks_taken = user_data.get('eat_breaks_today', 0)
    if eat_breaks_taken < MAX_EAT_BREAKS:
        keyboard_buttons.append('🍔 Eat')
        
    rest_breaks_taken = user_data.get('rest_breaks_today', 0)
    if rest_breaks_taken < MAX_REST_BREAKS:
        keyboard_buttons.append('🛌 Rest')

    # The "Off Work" button is always available after starting work.
    keyboard_buttons.append('👋 Off Work')
    
    # Arrange buttons into rows of 2 for a cleaner layout.
    # For example: [['🚽 Toilet', '🍔 Eat'], ['🛌 Rest', '👋 Off Work']]
    rows = [keyboard_buttons[i:i + 2] for i in range(0, len(keyboard_buttons), 2)]
    
    return rows
