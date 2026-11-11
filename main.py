import asyncio
import json
import logging
import signal
import sys
import time

import aiohttp

from config import (
    ADMIN_IDS,
    BOT_TOKEN,
    CHANNEL_ID,
    CHECK_INTERVAL,
    DATABASE_URL,
    ENABLE_FOURKHDHUB,
    ENABLE_MLSBD,
    ENABLE_MOVIESMOD,
    ENABLE_SKYMOVIES,
    ENABLE_VEGAMOVIES,
    INITIAL_MARK_SEEN,
    LEECH_BOT_USERNAME,
)
from database import db
from poster import post_movie_to_channel
from scrapers import fetch_all_sources
from web import start_web_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("Main")

IS_RUNNING = True
LAST_CHECK_TIME = 0


async def check_for_new_movies() -> int:
    """Fetch all sources, identify unseen movies, post them, and update database."""
    global LAST_CHECK_TIME
    LAST_CHECK_TIME = time.time()
    LOGGER.info("Starting check for new movie releases...")

    items = await fetch_all_sources()
    new_count = 0

    for item in items:
        if not IS_RUNNING:
            break

        is_already_seen = await db.is_seen(item.url)
        if not is_already_seen:
            LOGGER.info(f"New movie discovered: [{item.site}] {item.title}")
            # Mark seen first to prevent duplicate posting if crash occurs
            await db.mark_seen(item.url, item.title, item.site)
            # Post to channel
            success = await post_movie_to_channel(item)
            if success:
                new_count += 1
            # Avoid Telegram flood limits
            await asyncio.sleep(2)

    LOGGER.info(f"Check completed. Posted {new_count} new movie(s).")
    return new_count


async def monitor_loop():
    """Background monitoring loop running every CHECK_INTERVAL seconds."""
    # Handle initial run
    is_empty = await db.is_empty()
    if is_empty and INITIAL_MARK_SEEN:
        LOGGER.info("Initial boot detected with empty database! Fetching existing items to mark as seen...")
        items = await fetch_all_sources()
        for it in items:
            await db.mark_seen(it.url, it.title, it.site)
        LOGGER.info(
            f"Database initialized with {len(items)} existing movies. Bot is now watching for brand new releases!"
        )

        # Optionally post the latest 1 item to verify setup
        if items and BOT_TOKEN and CHANNEL_ID:
            LOGGER.info(f"Posting 1 sample latest release to verify channel setup: {items[0].title}")
            await post_movie_to_channel(items[0])

    LOGGER.info(f"Monitor loop activated! Interval: {CHECK_INTERVAL} seconds ({CHECK_INTERVAL // 60} mins).")

    while IS_RUNNING:
        try:
            await check_for_new_movies()
        except Exception as e:
            LOGGER.error(f"Error in monitor loop: {e}", exc_info=True)

        for _ in range(CHECK_INTERVAL):
            if not IS_RUNNING:
                break
            await asyncio.sleep(1)


async def bot_command_poller():
    """Lightweight command poller using Telegram getUpdates API for admin commands."""
    if not BOT_TOKEN:
        return

    LOGGER.info("Telegram Bot command listener started.")
    offset = 0
    timeout = aiohttp.ClientTimeout(total=40)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while IS_RUNNING:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                    data = await resp.json()
                    if not data.get("ok"):
                        await asyncio.sleep(5)
                        continue

                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message")
                        if not msg or "text" not in msg:
                            continue

                        text = msg["text"].strip()
                        chat_id = msg["chat"]["id"]
                        user_id = msg.get("from", {}).get("id", chat_id)

                        # Admin command check
                        is_admin = not ADMIN_IDS or user_id in ADMIN_IDS

                        if text in ("/start", "/help"):
                            reply = (
                                "🤖 <b>RDX Movie Feed Bot is Running!</b>\n\n"
                                f"📡 <b>Target Channel:</b> <code>{CHANNEL_ID}</code>\n"
                                f"⏱ <b>Check Interval:</b> {CHECK_INTERVAL}s\n"
                                f"🗄 <b>Database:</b> {'MongoDB' if DATABASE_URL else 'SQLite (Local)'}\n\n"
                                "<b>Commands:</b>\n"
                                "• /status - Show bot statistics & active sources\n"
                                "• /check or /force - Check for new movies now"
                            )
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML"},
                            )

                        elif text == "/status":
                            total = await db.get_total_count()
                            sources = []
                            if ENABLE_MLSBD:
                                sources.append("MLSBD")
                            if ENABLE_VEGAMOVIES:
                                sources.append("VegaMovies")
                            if ENABLE_FOURKHDHUB:
                                sources.append("4K-HDHub")
                            if ENABLE_MOVIESMOD:
                                sources.append("MoviesMod")
                            if ENABLE_SKYMOVIES:
                                sources.append("SkyMoviesHD")

                            last_time_str = (
                                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(LAST_CHECK_TIME))
                                if LAST_CHECK_TIME
                                else "Never"
                            )

                            reply = (
                                "📊 <b>RDX Movie Feed Status</b>\n\n"
                                f"🎬 <b>Total Movies Indexed:</b> <code>{total}</code>\n"
                                f"📡 <b>Channel ID:</b> <code>{CHANNEL_ID}</code>\n"
                                f"🌐 <b>Active Sources:</b> {', '.join(sources)}\n"
                                f"🕒 <b>Last Check:</b> {last_time_str}\n"
                                f"🤖 <b>Leech Bot:</b> @{LEECH_BOT_USERNAME or 'Not Set'}\n"
                                f"🗄 <b>DB Type:</b> {'MongoDB Atlas' if DATABASE_URL else 'SQLite (Local)'}"
                            )
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML"},
                            )

                        elif text in ("/check", "/force"):
                            if not is_admin:
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": chat_id, "text": "⛔ <i>Unauthorized admin command.</i>", "parse_mode": "HTML"},
                                )
                                continue

                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": "🔄 <i>Checking all sources for new movies now...</i>", "parse_mode": "HTML"},
                            )
                            count = await check_for_new_movies()
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"✅ Check finished! <b>{count}</b> new movie(s) posted to channel.",
                                    "parse_mode": "HTML",
                                },
                            )
            except Exception as e:
                LOGGER.debug(f"Poller error: {e}")
                await asyncio.sleep(5)


async def main():
    """Main entrypoint: starts Web Server, Monitor Loop, and Bot Command Poller."""
    LOGGER.info("Starting RDX Movie Feed Bot...")

    # Start health check server on 0.0.0.0:$PORT
    web_runner = await start_web_server()

    # Launch background tasks
    monitor_task = asyncio.create_task(monitor_loop())
    poller_task = asyncio.create_task(bot_command_poller())

    try:
        await asyncio.gather(monitor_task, poller_task)
    except asyncio.CancelledError:
        LOGGER.info("Tasks cancelled. Cleaning up...")
    finally:
        await web_runner.cleanup()
        LOGGER.info("Shutdown complete.")


if __name__ == "__main__":
    def signal_handler(sig, frame):
        global IS_RUNNING
        LOGGER.info("Termination signal received. Exiting...")
        IS_RUNNING = False
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    asyncio.run(main())
