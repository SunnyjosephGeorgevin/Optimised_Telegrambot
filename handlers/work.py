from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
import logging
from datetime import timedelta

from utils.time_utils import get_current_time, get_shift_date, format_duration
from utils.keyboards import main_keyboard, confirmation_keyboard
from utils.logger import log_activity

# --- Setup Logging ---
logger = logging.getLogger(__name__)

# --- State Definitions ---
SELECTING_ACTION, ON_BREAK, CONFIRM_OFF_WORK = range(3)

# --- Constants ---
WORK_START_HOUR = 11
WORK_START_MINUTE = 0

async def start_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the start of a work session, noting if the user is late or on time."""
    user = update.effective_user
    now = get_current_time()

    if context.user_data.get('work_started'):
        await update.message.reply_text("You have already started your work session.")
        return SELECTING_ACTION

    context.user_data['work_started'] = True
    context.user_data['work_start_time'] = now

    # Define the official start time for today's shift
    official_start_time = now.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
    
    timeliness_message = ""
    log_details = ""

    # --- SIMPLIFIED LOGIC: Handles Late or On-Time starts ---
    if now > official_start_time:
        late_by = now - official_start_time
        late_by_str = format_duration(late_by.total_seconds())
        timeliness_message = (
            f"❌ *Late Start:* Checked in at {now.strftime('%H:%M:%S')}\n"
            f"------------------------------------\n"
            f"⏰ You are late by {late_by_str}."
        )
        log_details = f"Checked in late by {late_by_str}."
    else:
        # This now covers both on-time and early starts without a special message
        timeliness_message = "✅ *On Time:* You have successfully checked in. Have a productive day! 🎉"
        log_details = "Checked in on time."

    shift_date_str = get_shift_date().strftime('%d-%m-%Y')
    
    response_message = (
        f"👤 *User:* {user.full_name}\n"
        f"🆔 *User ID:* {user.id}\n"
        f"------------------------------------\n"
        f"{timeliness_message}\n"
        f"------------------------------------\n"
        f"📅 Shift Date Recorded: {shift_date_str}"
    )

    log_activity(user, 'start_work', log_details)
    
    reply_markup = ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    await update.message.reply_text(response_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    return SELECTING_ACTION

async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for confirmation before checking out."""
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
    """Handles the final checkout process and generates the detailed report with overtime."""
    user = update.effective_user
    now = get_current_time()
    
    work_start_time = context.user_data.get('work_start_time')
    if not work_start_time:
        await update.message.reply_text("Error: Could not find your work start time. Please /start again.")
        return SELECTING_ACTION

    total_work_duration = (now - work_start_time).total_seconds()
    
    total_eat_duration = context.user_data.get('total_eat_duration', 0.0)
    total_toilet_duration = context.user_data.get('total_toilet_duration', 0.0)
    total_rest_duration = context.user_data.get('total_rest_duration', 0.0)
    total_break_duration = total_eat_duration + total_toilet_duration + total_rest_duration
    
    pure_work_duration = total_work_duration - total_break_duration

    eat_count = context.user_data.get('eat_breaks_today', 0)
    toilet_count = context.user_data.get('toilet_breaks_today', 0)
    rest_count = context.user_data.get('rest_breaks_today', 0)
    
    # --- Overtime Calculation ---
    overtime_message = ""
    # The shift officially ends at midnight (00:00) on the day AFTER the shift started.
    shift_end_time = (work_start_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))

    if now > shift_end_time:
        overtime_seconds = (now - shift_end_time).total_seconds()
        if overtime_seconds > 0:
            overtime_str = format_duration(overtime_seconds)
            overtime_message = f"🌙 *Overtime Worked:* {overtime_str}"
            # This correctly logs the overtime to your CSV file
            log_activity(user, 'work_overtime', f"Duration: {overtime_str}")

    report_lines = [
        f"👤 *User:* {user.full_name}\n🆔 *User ID:* {user.id}",
        "------------------------------------",
        f"✅ *Check-Out: Off Work* - {now.strftime('%d/%m %H:%M:%S')}",
        "------------------------------------",
        f"⏱️ Total work time: {format_duration(total_work_duration)}",
        f"⚙️ Pure work time: {format_duration(pure_work_duration)}",
        f"⏸️ Total break time: {format_duration(total_break_duration)}",
    ]
    
    if overtime_message:
        report_lines.append(overtime_message)

    report_lines.extend([
        "------------------------------------",
        f"🍔 Eat count: {eat_count} times ({format_duration(total_eat_duration)})",
        f"🚽 Toilet count: {toilet_count} times ({format_duration(total_toilet_duration)})",
        f"🛌 Rest count: {rest_count} times ({format_duration(total_rest_duration)})",
    ])

    report = "\n".join(report_lines)

    log_activity(user, 'off_work', f"Total work: {format_duration(total_work_duration)}, Pure work: {format_duration(pure_work_duration)}")
    
    await update.message.reply_text(report, reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_off_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the checkout process and returns to the main menu."""
    await update.message.reply_text(
        "Check-out cancelled. You are still on the clock.",
        reply_markup=ReplyKeyboardMarkup(main_keyboard(context.user_data), resize_keyboard=True)
    )
    return SELECTING_ACTION

