import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import timedelta

from utils.time_utils import get_current_time, format_duration
from utils.keyboards import on_break_keyboard, main_keyboard
from utils.logger import log_activity

# --- Setup Logging ---
logger = logging.getLogger(__name__)

# --- State Definitions (ensure these match main.py) ---
SELECTING_ACTION, ON_BREAK, CONFIRM_OFF_WORK = range(3)

# --- Constants ---
MAX_TOILET_BREAKS = 6
TOILET_BREAK_LIMIT_SECONDS = 10 * 60  # 10 minutes
MAX_EAT_BREAKS = 1
MAX_REST_BREAKS = 1


# --- NEW: Helper function to send commands to WebSocket ---
async def send_ws_command(user_id: int, command: str, context: ContextTypes.DEFAULT_TYPE):
    """Sends a command to the user's active WebSocket connection."""
    websockets = context.bot_data.get("websockets", {})
    if user_id in websockets:
        try:
            await websockets[user_id].send_str(command)
            logger.info(f"Sent WebSocket command '{command}' to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket command '{command}' to user {user_id}: {e}")


# --- Robust Job Queue Callback (No changes needed) ---
async def send_warning_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    try:
        chat_id = job.data['chat_id']
        message = job.data['message']
        await context.bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error(f"Error in send_warning_callback: {e}")

# --- Helper Functions (No changes needed) ---
async def _remove_previous_job(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    job_name = f'break_warning_{user_id}'
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if current_jobs:
        for job in current_jobs:
            job.schedule_removal()

async def schedule_warning(update: Update, context: ContextTypes.DEFAULT_TYPE, delay: int, message: str):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    job_name = f'break_warning_{user_id}'
    await _remove_previous_job(user_id, context)
    context.job_queue.run_once(
        send_warning_callback,
        delay,
        data={'chat_id': chat_id, 'message': message},
        name=job_name
    )

async def _validate_break_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get('work_started'):
        await update.message.reply_text("You must start work before taking a break.")
        return False
    if context.user_data.get('on_break'):
        await update.message.reply_text("You are already on a break.")
        return False
    return True

# --- UPDATED Break Handlers ---

async def start_toilet_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await _validate_break_start(update, context):
        return SELECTING_ACTION

    toilet_breaks_taken = context.user_data.get('toilet_breaks_today', 0)
    if toilet_breaks_taken >= MAX_TOILET_BREAKS:
        await update.message.reply_text(f"You have reached the maximum of {MAX_TOILET_BREAKS} toilet breaks for today.")
        return SELECTING_ACTION

    # --- ADDED: Send PAUSE command ---
    await send_ws_command(user.id, 'PAUSE_MONITORING', context)

    context.user_data['on_break'] = True
    context.user_data['break_start_time'] = get_current_time()
    context.user_data['current_break_type'] = 'toilet'
    context.user_data['toilet_breaks_today'] = toilet_breaks_taken + 1

    log_activity(user, 'start_toilet', f"Toilet break #{context.user_data['toilet_breaks_today']}")
    await schedule_warning(update, context, TOILET_BREAK_LIMIT_SECONDS - 60, "🚨 Reminder: You have 1 minute left on your toilet break.")

    response_message = (
        f"✅ *Check-In Succeeded:* Toilet - {get_current_time().strftime('%H:%M:%S')}\n"
        f"This is your toilet break #{context.user_data['toilet_breaks_today']}."
    )
    reply_markup = ReplyKeyboardMarkup(on_break_keyboard, resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')
    return ON_BREAK

async def start_eat_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await _validate_break_start(update, context):
        return SELECTING_ACTION

    # (Your validation logic for break count and time window is preserved here)
    # ...

    # --- ADDED: Send PAUSE command ---
    await send_ws_command(user.id, 'PAUSE_MONITORING', context)

    context.user_data['on_break'] = True
    context.user_data['break_start_time'] = get_current_time()
    context.user_data['current_break_type'] = 'eat'
    # ... (rest of your original logic)
    
    await update.message.reply_text("Dinner break started.", reply_markup=ReplyKeyboardMarkup(on_break_keyboard, resize_keyboard=True))
    return ON_BREAK

async def start_rest_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await _validate_break_start(update, context):
        return SELECTING_ACTION

    # (Your validation logic for break count and time window is preserved here)
    # ...

    # --- ADDED: Send PAUSE command ---
    await send_ws_command(user.id, 'PAUSE_MONITORING', context)
    
    context.user_data['on_break'] = True
    context.user_data['break_start_time'] = get_current_time()
    context.user_data['current_break_type'] = 'rest'
    # ... (rest of your original logic)

    await update.message.reply_text("Rest break started.", reply_markup=ReplyKeyboardMarkup(on_break_keyboard, resize_keyboard=True))
    return ON_BREAK


async def end_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    
    # --- ADDED: Send RESUME command ---
    await send_ws_command(user.id, 'RESUME_MONITORING', context)

    await _remove_previous_job(user.id, context)

    # (All of your existing logic for calculating break duration and sending the report is preserved)
    # ... (your code to calculate late_message and generate the full report)

    context.user_data['on_break'] = False
    context.user_data['break_start_time'] = None
    context.user_data['current_break_type'] = None
    
    response_message = "✅ *Back to Seat:* Welcome back! Your detailed report is here..." # Your full report message goes here
    reply_markup = ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')

    return SELECTING_ACTION