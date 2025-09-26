"""
Handlers for admin-only bot commands.
"""
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import admin_only

# Configure logging
logger = logging.getLogger(__name__)

# The log file name must match the one in utils/logger.py
LOG_FILE = 'work_tracker_log.csv'

@admin_only
async def get_log_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Allows the admin to download the work tracker log file.
    This handler is protected by the @admin_only decorator.
    """
    user = update.effective_user
    logger.info(f"Admin user {user.id} ({user.username}) requested the log file.")
    
    if not os.path.exists(LOG_FILE):
        await update.message.reply_text("The log file does not exist yet. It will be created after the first activity is logged.")
        return

    try:
        # This is the improved part: using 'with' to handle the file
        with open(LOG_FILE, 'rb') as document:
            await context.bot.send_document(
                chat_id=user.id,
                document=document,
                filename='work_tracker_log.csv',
                caption='Here is the latest work tracker log file.'
            )
        logger.info(f"Log file successfully sent to admin {user.id}.")
    except Exception as e:
        logger.error(f"Failed to send log file to admin {user.id}: {e}")
        await update.message.reply_text("An error occurred while trying to send the log file.")

