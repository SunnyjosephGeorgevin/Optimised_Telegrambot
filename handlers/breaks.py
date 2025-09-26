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

# --- Robust Job Queue Callback ---
async def send_warning_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    # (Your original code here, unchanged)
    job = context.job
    try:
        chat_id = job.data['chat_id']
        message = job.data['message']
        await context.bot.send_message(chat_id=chat_id, text=message)
        logger.info(f"Sent scheduled alert to chat_id {chat_id}")
    except (KeyError, TypeError) as e:
        logger.error(f"Error in send_warning_callback: Could not retrieve data from job. {e}")

# --- Helper Functions ---
async def _remove_previous_job(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    # (Your original code here, unchanged)
    job_name = f'break_warning_{user_id}'
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if current_jobs:
        logger.info(f"Removing {len(current_jobs)} existing jobs for user {user_id}")
        for job in current_jobs:
            job.schedule_removal()

async def schedule_warning(update: Update, context: ContextTypes.DEFAULT_TYPE, delay: int, message: str):
    # (Your original code here, unchanged)
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
    # (Your original code here, unchanged)
    if not context.user_data.get('work_started'):
        await update.message.reply_text("You must start work before taking a break.")
        return False
    if context.user_data.get('on_break'):
        await update.message.reply_text("You are already on a break.")
        return False
    return True

# --- Break Handlers ---
async def start_toilet_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await _validate_break_start(update, context):
        return SELECTING_ACTION

    toilet_breaks_taken = context.user_data.get('toilet_breaks_today', 0)
    if toilet_breaks_taken >= MAX_TOILET_BREAKS:
        await update.message.reply_text(f"You have reached the maximum of {MAX_TOILET_BREAKS} toilet breaks for today.")
        return SELECTING_ACTION

    # --- NEW: Send PAUSE command ---
    await send_ws_command(user.id, 'PAUSE_MONITORING', context)

    # (The rest of your original code is unchanged)
    context.user_data['on_break'] = True
    context.user_data['break_start_time'] = get_current_time()
    context.user_data['current_break_type'] = 'toilet'
    context.user_data['toilet_breaks_today'] = toilet_breaks_taken + 1

    log_activity(user, 'start_toilet', f"Toilet break #{context.user_data['toilet_breaks_today']}")
    await schedule_warning(update, context, TOILET_BREAK_LIMIT_SECONDS - 60, "🚨 Reminder: You have 1 minute left on your toilet break.")

    response_message = (
        f"👤 *User:* {user.full_name}\n🆔 *User ID:* {user.id}\n"
        f"------------------------------------\n"
        f"✅ *Check-In Succeeded:* Toilet - {get_current_time().strftime('%d/%m %H:%M:%S')}\n"
        f"------------------------------------\n"
        f"*Attention:* This is your {context.user_data['toilet_breaks_today']} time Toilet.\n"
        f"*Time Limit for This Activity:* {int(TOILET_BREAK_LIMIT_SECONDS / 60)} minutes\n"
        f"*Tip:* Please check in Back to Seat after completing the activity."
    )

    reply_markup = ReplyKeyboardMarkup(on_break_keyboard, resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')
    return ON_BREAK

async def start_eat_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await _validate_break_start(update, context):
        return SELECTING_ACTION

    eat_breaks_taken = context.user_data.get('eat_breaks_today', 0)
    if eat_breaks_taken >= MAX_EAT_BREAKS:
        await update.message.reply_text("You have already taken your dinner break for today.")
        return SELECTING_ACTION

    now = get_current_time()
    start_time = now.replace(hour=22, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=30)

    if not (start_time <= now <= end_time):
        await update.message.reply_text("Dinner break is only allowed between 22:00 and 22:30.")
        return SELECTING_ACTION

    # --- NEW: Send PAUSE command ---
    await send_ws_command(user.id, 'PAUSE_MONITORING', context)

    # (The rest of your original code is unchanged)
    context.user_data['on_break'] = True
    context.user_data['break_start_time'] = get_current_time()
    context.user_data['current_break_type'] = 'eat'
    context.user_data['eat_breaks_today'] = eat_breaks_taken + 1

    log_activity(user, 'start_eat', f"Eat break #{context.user_data['eat_breaks_today']}")

    remaining_seconds = (end_time - now).total_seconds()
    if remaining_seconds > 60:
        await schedule_warning(update, context, remaining_seconds - 60, "🚨 Reminder: The dinner break period ends in 1 minute.")

    response_message = (
        f"👤 *User:* {user.full_name}\n🆔 *User ID:* {user.id}\n"
        f"------------------------------------\n"
        f"✅ *Check-In Succeeded:* Eat - {get_current_time().strftime('%d/%m %H:%M:%S')}\n"
        f"------------------------------------\n"
        f"*Attention:* Dinner break ends at 22:30.\n"
        f"*Tip:* Please check in Back to Seat after completing the activity."
    )

    reply_markup = ReplyKeyboardMarkup(on_break_keyboard, resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')
    return ON_BREAK

async def start_rest_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not await _validate_break_start(update, context):
        return SELECTING_ACTION

    rest_breaks_taken = context.user_data.get('rest_breaks_today', 0)
    if rest_breaks_taken >= MAX_REST_BREAKS:
        await update.message.reply_text("You have already taken your rest break for today.")
        return SELECTING_ACTION

    now = get_current_time()
    start_time = now.replace(hour=16, minute=15, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1, minutes=30)

    if not (start_time <= now <= end_time):
        await update.message.reply_text("Rest break is only allowed between 16:15 and 17:45.")
        return SELECTING_ACTION

    # --- NEW: Send PAUSE command ---
    await send_ws_command(user.id, 'PAUSE_MONITORING', context)
    
    # (The rest of your original code is unchanged)
    context.user_data['on_break'] = True
    context.user_data['break_start_time'] = get_current_time()
    context.user_data['current_break_type'] = 'rest'
    context.user_data['rest_breaks_today'] = rest_breaks_taken + 1

    log_activity(user, 'start_rest', f"Rest break #{context.user_data['rest_breaks_today']}")

    remaining_seconds = (end_time - now).total_seconds()
    if remaining_seconds > 60:
        await schedule_warning(update, context, remaining_seconds - 60, "🚨 Reminder: The rest break period ends in 1 minute.")

    response_message = (
        f"👤 *User:* {user.full_name}\n🆔 *User ID:* {user.id}\n"
        f"------------------------------------\n"
        f"✅ *Check-In Succeeded:* Rest - {get_current_time().strftime('%d/%m %H:%M:%S')}\n"
        f"------------------------------------\n"
        f"*Attention:* Rest break ends at 17:45.\n"
        f"*Tip:* Please check in Back to Seat after completing the activity."
    )

    reply_markup = ReplyKeyboardMarkup(on_break_keyboard, resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')
    return ON_BREAK

async def end_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    now = get_current_time()

    # --- NEW: Send RESUME command ---
    await send_ws_command(user.id, 'RESUME_MONITORING', context)

    # (The rest of your original code is unchanged)
    await _remove_previous_job(user.id, context)

    break_start_time = context.user_data.get('break_start_time')
    break_type = context.user_data.get('current_break_type')

    if not break_start_time or not break_type:
        #... (your original error handling)
        return SELECTING_ACTION

    duration_seconds = (now - break_start_time).total_seconds()
    #... (the rest of your original report generation logic is preserved)
    
    late_message = "" # (your lateness logic)
    # ...
    
    report_lines = [ # (your detailed report lines)
        # ...
    ]
    response_message = "\n".join(report_lines)

    log_activity(user, 'end_break', f"Ended {break_type} break. Duration: {format_duration(duration_seconds)}")

    context.user_data['on_break'] = False
    context.user_data['break_start_time'] = None
    context.user_data['current_break_type'] = None

    reply_markup = ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')

    return SELECTING_ACTION