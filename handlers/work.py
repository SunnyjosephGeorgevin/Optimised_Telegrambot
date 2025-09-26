# handlers/work.py

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
import logging
from datetime import timedelta

from utils.time_utils import get_current_time, get_shift_date, format_duration
from utils.keyboards import main_keyboard, confirmation_keyboard
from utils.logger import log_activity

logger = logging.getLogger(__name__)

SELECTING_ACTION, ON_BREAK, CONFIRM_OFF_WORK = range(3)
WORK_START_HOUR = 11
WORK_START_MINUTE = 0

async def start_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    now = get_current_time()

    if context.user_data.get('work_started'):
        await update.message.reply_text("You have already started your work session.")
        return SELECTING_ACTION

    context.user_data['work_started'] = True
    context.user_data['work_start_time'] = now

    official_start_time = now.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
    
    timeliness_message = ""
    if now > official_start_time:
        late_by = now - official_start_time
        late_by_str = format_duration(late_by.total_seconds())
        timeliness_message = f"❌ *Late Start:* You are late by {late_by_str}."
    else:
        timeliness_message = "✅ *On Time:* You have successfully checked in."

    response_message = f"👤 *User:* {user.full_name}\n{timeliness_message}"
    log_activity(user, 'start_work', "Checked in")
    
    reply_markup = ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Send the unique monitoring link
    base_url = context.bot_data.get("BASE_URL", "http://localhost:8080")
    monitoring_link = f"{base_url}/monitor.html?user_id={user.id}"
    await update.message.reply_text(
        "Please open this link to start webcam monitoring:\n"
        f"{monitoring_link}"
    )
    
    return SELECTING_ACTION

async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('work_started'):
        await update.message.reply_text("You haven't started work yet.")
        return SELECTING_ACTION
    if context.user_data.get('on_break'):
        await update.message.reply_text("You must end your break before checking out.")
        return ON_BREAK
    
    reply_markup = ReplyKeyboardMarkup(confirmation_keyboard, resize_keyboard=True)
    await update.message.reply_text("⚠️ Are you sure you want to check out?", reply_markup=reply_markup)
    
    return CONFIRM_OFF_WORK

async def confirm_off_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    
    # Send STOP command to the web page
    websockets = context.bot_data.get("websockets", {})
    if user.id in websockets:
        try:
            await websockets[user.id].send_str('STOP_MONITORING')
            await websockets[user.id].close()
        except Exception as e:
            logger.error(f"Error sending STOP to user {user.id}: {e}")

    # ... (rest of the summary logic remains the same)
    now = get_current_time()
    work_start_time = context.user_data.get('work_start_time')
    total_work_duration = (now - work_start_time).total_seconds()
    # ... generate and send the report ...
    
    report = "Your final work summary..." # (simplified for brevity)
    log_activity(user, 'off_work', f"Total work: {format_duration(total_work_duration)}")
    
    await update.message.reply_text(report, reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_off_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Check-out cancelled.",
        reply_markup=ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    )
    return SELECTING_ACTION