import asyncio
import json
import logging
import os
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
    FOURKHDHUB_URL,
    INITIAL_MARK_SEEN,
    LEECH_BOTS,
    MLSBD_FEED,
    MOVIESMOD_URL,
    SKYBAP_URL,
    SKYMOVIES_URL,
    VEGAMOVIES_URL,
)
from database import db
from poster import post_movie_to_channel
from scrapers import fetch_all_sources
from scrapers.skymovieshd import resolve_active_domain
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
RESTART_FILE = os.path.join(os.path.dirname(__file__), "data", "restart.json")


async def setup_bot_commands(session: aiohttp.ClientSession):
    """Register official Telegram Bot Menu commands with setMyCommands."""
    if not BOT_TOKEN:
        return
    commands = [
        {"command": "start", "description": "Open bot control panel"},
        {"command": "status", "description": "View system status & statistics"},
        {"command": "check", "description": "Force check for new releases now"},
        {"command": "sources", "description": "Show monitored sites & domains"},
        {"command": "restart", "description": "Restart the bot service"},
    ]
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
        async with session.post(url, json={"commands": commands}) as resp:
            data = await resp.json()
            if data.get("ok"):
                LOGGER.info("Registered Telegram menu commands successfully.")
            else:
                LOGGER.warning(f"setMyCommands failed: {data.get('description')}")
    except Exception as e:
        LOGGER.error(f"Error registering menu commands: {e}")


async def check_restart_notification(session: aiohttp.ClientSession):
    """Check if bot just rebooted from /restart and notify admin."""
    if not os.path.exists(RESTART_FILE):
        return
    try:
        with open(RESTART_FILE, "r") as f:
            info = json.load(f)
        os.remove(RESTART_FILE)

        chat_id = info.get("chat_id")
        msg_id = info.get("message_id")
        restart_time = info.get("time", 0)
        elapsed = f"{(time.time() - restart_time):.1f}s" if restart_time else "few seconds"

        text = f"✅ <b>RDX Movie Feed Bot restarted successfully!</b>\n⏱ <i>Reboot took {elapsed}</i>"
        if msg_id:
            edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
            await session.post(
                edit_url,
                json={"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"},
            )
        else:
            send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            await session.post(
                send_url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        LOGGER.error(f"Error processing restart notification: {e}")


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
    is_empty = await db.is_empty()
    if is_empty and INITIAL_MARK_SEEN:
        LOGGER.info("Initial boot detected with empty database! Fetching existing items to mark as seen...")
        items = await fetch_all_sources()
        for it in items:
            await db.mark_seen(it.url, it.title, it.site)
        LOGGER.info(
            f"Database initialized with {len(items)} existing movies. Bot is now watching for brand new releases!"
        )

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


def get_panel_keyboard() -> dict:
    """Inline keyboard for the bot control panel."""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Bot Status", "callback_data": "panel_status"},
                {"text": "🔄 Check Now", "callback_data": "panel_check"},
            ],
            [
                {"text": "🌐 Active Domains", "callback_data": "panel_sources"},
                {"text": "🔁 Restart Bot", "callback_data": "panel_restart"},
            ],
        ]
    }


async def generate_status_text() -> str:
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

    bots_str = ", ".join([f"@{b}" for b in LEECH_BOTS]) if LEECH_BOTS else "None configured"

    return (
        "📊 <b>RDX Movie Feed Status</b>\n\n"
        f"🎬 <b>Total Movies Indexed:</b> <code>{total}</code>\n"
        f"📡 <b>Target Channel:</b> <code>{CHANNEL_ID}</code>\n"
        f"🌐 <b>Active Sources ({len(sources)}):</b> {', '.join(sources)}\n"
        f"🤖 <b>Leech Bots:</b> {bots_str}\n"
        f"🕒 <b>Last Check:</b> {last_time_str}\n"
        f"⏱ <b>Interval:</b> {CHECK_INTERVAL}s\n"
        f"🗄 <b>DB Type:</b> {'MongoDB Atlas' if DATABASE_URL else 'SQLite (Local)'}"
    )


async def generate_sources_text() -> str:
    sky_domain = await resolve_active_domain()
    return (
        "🌐 <b>Active Monitored Sources & Domains</b>\n\n"
        f"🇧🇩 <b>MLSBD:</b> <code>{MLSBD_FEED}</code>\n"
        f"⭐ <b>VegaMovies:</b> <code>{VEGAMOVIES_URL}</code>\n"
        f"💎 <b>4K-HDHub:</b> <code>{FOURKHDHUB_URL}</code>\n"
        f"⚡ <b>MoviesMod:</b> <code>{MOVIESMOD_URL}</code>\n"
        f"☁️ <b>SkyMoviesHD:</b> <code>{sky_domain}</code>\n"
        f"   └ <i>Auto-resolver: {SKYBAP_URL}</i>\n\n"
        "💡 <i>All domains can be customized via .env or Config Vars!</i>"
    )


async def restart_bot(session: aiohttp.ClientSession, chat_id: int):
    """Gracefully restart the bot process."""
    msg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🔄 <b>Restarting RDX Movie Feed Bot...</b>\n<i>Please wait a few seconds.</i>",
        "parse_mode": "HTML",
    }
    msg_id = None
    try:
        async with session.post(msg_url, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
    except Exception:
        pass

    # Save restart state
    os.makedirs(os.path.dirname(RESTART_FILE), exist_ok=True)
    with open(RESTART_FILE, "w") as f:
        json.dump({"chat_id": chat_id, "message_id": msg_id, "time": time.time()}, f)

    LOGGER.info("Executing process reboot via execl...")
    # Give a tiny breath for message delivery
    await asyncio.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)


async def bot_command_poller():
    """Command & Callback poller using Telegram getUpdates API."""
    if not BOT_TOKEN:
        return

    LOGGER.info("Telegram Bot command listener started.")
    offset = 0
    timeout = aiohttp.ClientTimeout(total=45)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Register bot commands menu on startup
        await setup_bot_commands(session)
        # Check if rebooted from /restart
        await check_restart_notification(session)

        while IS_RUNNING:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(4)
                        continue
                    data = await resp.json()
                    if not data.get("ok"):
                        await asyncio.sleep(4)
                        continue

                    for update in data.get("result", []):
                        offset = update["update_id"] + 1

                        # 1. Handle Callback Queries (Inline Buttons)
                        cb = update.get("callback_query")
                        if cb:
                            cb_id = cb["id"]
                            cb_data = cb.get("data", "")
                            cb_user_id = cb["from"]["id"]
                            cb_chat_id = cb["message"]["chat"]["id"]
                            cb_msg_id = cb["message"]["message_id"]

                            is_admin = not ADMIN_IDS or cb_user_id in ADMIN_IDS

                            # Answer callback to remove loading wheel
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                                json={"callback_query_id": cb_id},
                            )

                            if cb_data == "panel_status":
                                text = await generate_status_text()
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                                    json={
                                        "chat_id": cb_chat_id,
                                        "message_id": cb_msg_id,
                                        "text": text,
                                        "parse_mode": "HTML",
                                        "reply_markup": get_panel_keyboard(),
                                    },
                                )
                            elif cb_data == "panel_sources":
                                text = await generate_sources_text()
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                                    json={
                                        "chat_id": cb_chat_id,
                                        "message_id": cb_msg_id,
                                        "text": text,
                                        "parse_mode": "HTML",
                                        "reply_markup": get_panel_keyboard(),
                                    },
                                )
                            elif cb_data == "panel_check":
                                if not is_admin:
                                    continue
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": cb_chat_id, "text": "🔄 <i>Checking all sources now...</i>", "parse_mode": "HTML"},
                                )
                                count = await check_for_new_movies()
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": cb_chat_id, "text": f"✅ Check complete! <b>{count}</b> new release(s) posted.", "parse_mode": "HTML"},
                                )
                            elif cb_data == "panel_restart":
                                if not is_admin:
                                    continue
                                await restart_bot(session, cb_chat_id)
                            continue

                        # 2. Handle Text Messages
                        msg = update.get("message")
                        if not msg or "text" not in msg:
                            continue

                        text = msg["text"].strip()
                        chat_id = msg["chat"]["id"]
                        user_id = msg.get("from", {}).get("id", chat_id)
                        is_admin = not ADMIN_IDS or user_id in ADMIN_IDS

                        if text in ("/start", "/help", "/panel"):
                            bots_count = len(LEECH_BOTS)
                            reply = (
                                "🤖 <b>RDX Movie Feed Bot Control Panel</b>\n\n"
                                f"📡 <b>Target Channel:</b> <code>{CHANNEL_ID}</code>\n"
                                f"🤖 <b>Configured Leech Bots:</b> <code>{bots_count}</code>\n"
                                f"⏱ <b>Check Frequency:</b> Every {CHECK_INTERVAL}s\n"
                                f"🗄 <b>Database Engine:</b> {'MongoDB Atlas' if DATABASE_URL else 'SQLite (Local)'}\n\n"
                                "<i>Select an option below to manage the feed bot:</i>"
                            )
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": reply,
                                    "parse_mode": "HTML",
                                    "reply_markup": get_panel_keyboard(),
                                },
                            )

                        elif text == "/status":
                            reply = await generate_status_text()
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML", "reply_markup": get_panel_keyboard()},
                            )

                        elif text == "/sources":
                            reply = await generate_sources_text()
                            await session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML", "reply_markup": get_panel_keyboard()},
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

                        elif text == "/restart":
                            if not is_admin:
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": chat_id, "text": "⛔ <i>Unauthorized admin command.</i>", "parse_mode": "HTML"},
                                )
                                continue
                            await restart_bot(session, chat_id)

            except Exception as e:
                LOGGER.debug(f"Poller error: {e}")
                await asyncio.sleep(4)


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
