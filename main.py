import asyncio
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    PicklePersistence,
)

from aiohttp import web

# --- Import your custom handlers ---
from handlers import start, work, breaks, admin

# --- Setup Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- State Definitions for ConversationHandler ---
SELECTING_ACTION, ON_BREAK, CONFIRM_OFF_WORK = range(3)


# --- Web Server Part (to keep Render service alive) ---
async def health_check(request):
    return web.Response(text="Health check: OK, I am alive!")

async def run_web_server(port):
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    logger.info(f"Starting web server on port {port}...")
    await site.start()
    logger.info("Web server started successfully.")


# --- Main Application Logic ---
async def main() -> None:
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("FATAL: BOT_TOKEN environment variable not set!")
        return

    PORT = int(os.environ.get("PORT", 8080))

    # --- Setup Persistence ---
    persistence = PicklePersistence(filepath="bot_persistence")

    application = (
        Application.builder()
        .token(TOKEN)
        .persistence(persistence)
        .build()
    )

    # --- Setup Conversation Handler with Persistence ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start.start)],
        states={
            SELECTING_ACTION: [
                MessageHandler(filters.Regex('^🚀 Start Work$'), work.start_work),
                MessageHandler(filters.Regex('^👋 Off Work$'), work.off_work),
                MessageHandler(filters.Regex('^🚽 Toilet$'), breaks.start_toilet_break),
                MessageHandler(filters.Regex('^🍔 Eat$'), breaks.start_eat_break),
                MessageHandler(filters.Regex('^🛌 Rest$'), breaks.start_rest_break),
            ],
            ON_BREAK: [
                MessageHandler(filters.Regex('^🏃 Back to Seat$'), breaks.end_break),
            ],
            CONFIRM_OFF_WORK: [
                MessageHandler(filters.Regex('^✅ Yes$'), work.confirm_off_work),
                MessageHandler(filters.Regex('^❌ No$'), work.cancel_off_work),
            ],
        },
        fallbacks=[CommandHandler('start', start.start)],
        # --- THIS IS THE CRITICAL FIX ---
        persistent=True,
        name="main_conversation_handler" # A unique name for the handler
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('getlog', admin.get_log_file))

    # --- Run bot and web server concurrently ---
    logger.info("Starting bot with long polling...")
    async with application:
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await run_web_server(PORT)
        await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())

