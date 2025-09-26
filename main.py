import asyncio
import logging
import os

from telegram import Update, User
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
# --- Import the logger utility ---
from utils.logger import log_activity

# --- Setup Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- State Definitions for ConversationHandler ---
SELECTING_ACTION, ON_BREAK, CONFIRM_OFF_WORK = range(3)

# --- A dictionary to store active WebSocket connections for each user ---
websockets = {}


# --- Web Server Part (to keep Render service alive) ---
async def health_check(request):
    """A simple health check endpoint."""
    return web.Response(text="Health check: OK, I am alive!")

async def websocket_handler(request):
    """Handles WebSocket connections from the monitoring web page."""
    user_id_str = request.query.get('user_id')
    if not user_id_str or not user_id_str.isdigit():
        logger.error("WebSocket connection attempt without a valid user_id.")
        return web.Response(status=400, text="user_id is required.")
        
    user_id = int(user_id_str)
    
    # Get the bot application from the web app context
    application = request.app['bot_app']

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    websockets[user_id] = ws
    logger.info(f"WebSocket connection opened for user_id: {user_id}")
    
    # Fetch user details to use for logging
    try:
        user_chat = await application.bot.get_chat(user_id)
        # Create a mock User object for the logger function
        log_user = User(id=user_id, first_name=user_chat.first_name, is_bot=False, username=user_chat.username)
    except Exception as e:
        logger.error(f"Could not fetch user details for {user_id}: {e}")
        log_user = User(id=user_id, first_name=str(user_id), is_bot=False)


    try:
        # This loop waits for messages from the client web page
        async for msg in ws:
            status = msg.data
            logger.info(f"Received message from user {user_id}: {status}")
            
            # --- THIS IS THE NEW LOGIC ---
            if status == 'ACTIVE':
                log_activity(log_user, 'status_active', 'Webcam detected presence')
            elif status == 'IDLE':
                log_activity(log_user, 'status_idle', 'Webcam detected absence (unregistered break)')

    finally:
        logger.info(f"WebSocket connection closed for user_id: {user_id}")
        if user_id in websockets:
            del websockets[user_id]
            
    return ws


async def run_web_server(port, application):
    """Initializes and runs the web server."""
    app = web.Application()
    # Make the bot application instance available to handlers
    app['bot_app'] = application

    app.router.add_get('/', health_check)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/monitor.html', lambda r: web.FileResponse('monitor.html'))
    app.router.add_static('/models', 'models')
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    logger.info(f"Starting web server on port {port}...")
    await site.start()
    logger.info("Web server started successfully.")


# --- Main Application Logic ---
async def main() -> None:
    """The main entry point for the bot."""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("FATAL: BOT_TOKEN environment variable not set!")
        return

    PORT = int(os.environ.get("PORT", 8080))
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

    persistence = PicklePersistence(filepath="bot_persistence")

    application = (
        Application.builder()
        .token(TOKEN)
        .persistence(persistence)
        .build()
    )
    
    application.bot_data["BASE_URL"] = BASE_URL
    application.bot_data["websockets"] = websockets

    # (Your ConversationHandler remains exactly the same)
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
        persistent=True,
        name="main_conversation_handler"
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('getlog', admin.get_log_file))

    logger.info("Starting bot with long polling...")
    async with application:
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        # Pass the application instance to the web server
        await run_web_server(PORT, application)
        await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())