from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.auth import restricted
from utils.keyboards import main_keyboard
import logging

# --- Setup Logging ---
logger = logging.getLogger(__name__)

# --- State Definitions ---
SELECTING_ACTION, ON_BREAK = range(2)

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the bot, displays a welcome message, and clears old data."""
    user = update.effective_user
    context.user_data.clear()

    # --- Initialize User Data for Detailed Tracking ---
    context.user_data['work_started'] = False
    context.user_data['on_break'] = False
    context.user_data['break_start_time'] = None
    context.user_data['current_break_type'] = None
    context.user_data['active_warning_job'] = None
    
    # Initialize separate break counters and durations
    context.user_data['toilet_breaks_today'] = 0
    context.user_data['eat_breaks_today'] = 0
    context.user_data['rest_breaks_today'] = 0
    context.user_data['total_toilet_duration'] = 0.0
    context.user_data['total_eat_duration'] = 0.0
    context.user_data['total_rest_duration'] = 0.0
    context.user_data['total_break_duration'] = 0.0 # Overall total

    logger.info(f"User {user.id} ({user.first_name}) started a new session.")

    # Send welcome message with the initial keyboard
    reply_markup = ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    await update.message.reply_text(
        "Welcome to the Work Tracker Bot! Please choose an action.",
        reply_markup=reply_markup
    )

    return SELECTING_ACTION

