"""
Authorization decorators to restrict access to certain handlers.
"""
import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import logging

# Configure logging
logger = logging.getLogger(__name__)

# --- Regular User Authorization ---
ALLOWED_USER_IDS_STR = os.getenv('ALLOWED_USER_IDS')
if not ALLOWED_USER_IDS_STR:
    logger.warning("ALLOWED_USER_IDS environment variable is not set. No users will be authorized.")
    ALLOWED_IDS = set()
else:
    try:
        # Read comma-separated IDs and convert them to a set of integers
        ALLOWED_IDS = {int(user_id.strip()) for user_id in ALLOWED_USER_IDS_STR.split(',')}
        logger.info(f"Authorization enabled for user IDs: {ALLOWED_IDS}")
    except ValueError:
        logger.error("ALLOWED_USER_IDS environment variable contains non-integer values. Authorization will fail.")
        ALLOWED_IDS = set()

def restricted(func):
    """Decorator to restrict usage of a handler to authorized users."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in ALLOWED_IDS:
            if user:
                logger.warning(f"Unauthorized access attempt by user ID: {user.id} ({user.username}).")
                await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            else:
                logger.warning("Unauthorized access attempt with no effective_user.")
            return # Block the function
        return await func(update, context, *args, **kwargs) # Allow the function
    return wrapped

# --- Admin User Authorization ---
ADMIN_ID_STR = os.getenv('ADMIN_ID')
ADMIN_ID = None
if not ADMIN_ID_STR:
    logger.warning("ADMIN_ID environment variable is not set. Admin commands will not work.")
else:
    try:
        # Read the single admin ID and convert it to an integer
        ADMIN_ID = int(ADMIN_ID_STR.strip())
        logger.info(f"Admin commands enabled for admin ID: {ADMIN_ID}")
    except ValueError:
        logger.error("ADMIN_ID environment variable is not a valid integer. Admin commands will fail.")

def admin_only(func):
    """Decorator to restrict usage of a handler to the admin only."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id != ADMIN_ID:
            if user:
                logger.warning(f"Non-admin user {user.id} ({user.username}) attempted to use an admin command.")
                # We don't send a message back to avoid revealing admin commands exist.
            else:
                 logger.warning("Unauthorized admin command attempt with no effective_user.")
            return # Block the function
        return await func(update, context, *args, **kwargs) # Allow the function
    return wrapped

