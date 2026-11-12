import asyncio
import json
import logging
import os
import signal
import sys
import time
from typing import Optional

import aiohttp

from html import escape
from urllib.parse import quote
import uuid

from config import (
    ADMIN_IDS,
    BOLLYFLIX_HUB_URL,
    BOLLYFLIX_URL,
    BOT_TOKEN,
    CHANNEL_ID,
    CHECK_INTERVAL,
    CINEVOOD_HUB_URL,
    CINEVOOD_URL,
    DATABASE_URL,
    DOTMOVIES_HUB_URL,
    DOTMOVIES_URL,
    ENABLE_BOLLYFLIX,
    ENABLE_CINEVOOD,
    ENABLE_DOTMOVIES,
    ENABLE_EXTRAFLIX,
    ENABLE_FOURKHDHUB,
    ENABLE_HDHUB4U,
    ENABLE_KATDRAMA,
    ENABLE_KATMOVIEHD,
    ENABLE_MLSBD,
    ENABLE_MOVIESMOD,
    ENABLE_SKYMOVIES,
    ENABLE_TOONWORLD,
    ENABLE_VEGAMOVIES,
    EXTRAFLIX_HUB_URL,
    EXTRAFLIX_URL,
    FOURKHDHUB_URL,
    HDHUB4U_HUB_URL,
    HDHUB4U_URL,
    INITIAL_MARK_SEEN,
    KATDRAMA_URL,
    KATMOVIEHD_HUB_URL,
    KATMOVIEHD_URL,
    LEECH_BOTS,
    LEECH_BOT_USERNAME,
    MLSBD_FEED,
    MODLIST_HUB_URL,
    MOVIESMOD_URL,
    SKYBAP_URL,
    SKYMOVIES_URL,
    TOONWORLD_URL,
    VEGA_HUB_URL,
    VEGAMOVIES_URL,
)
from database import db
from poster import post_movie_to_channel
from scrapers import fetch_all_sources
from scrapers.base import MovieItem
from scrapers.bollyflix import resolve_active_bollyflix_domain
from scrapers.cinevood import resolve_active_cinevood_domain
from scrapers.dotmovies import resolve_active_dotmovies_domain
from scrapers.extraflix import resolve_active_extraflix_domain
from scrapers.hdhub4u import resolve_active_hdhub4u_domain
from scrapers.katdrama import resolve_active_katdrama_domain
from scrapers.katmoviehd import resolve_active_katmoviehd_domain
from scrapers.moviesmod import resolve_active_moviesmod_domain
from scrapers.skymovieshd import resolve_active_domain
from scrapers.toonworld import resolve_active_toonworld_domain
from scrapers.vegamovies import resolve_active_vega_domain
from search import search_all_sites
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
        {"command": "search", "description": "Search movies, series & anime"},
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


# ── Search Engine State & UI ──────────────────────────────────────────────────
SEARCH_CACHE = {}
SEARCH_TTL = 1800  # 30 minutes


def clean_search_cache():
    now = time.time()
    for sid in list(SEARCH_CACHE.keys()):
        if now - SEARCH_CACHE[sid].get("ts", 0) > SEARCH_TTL:
            SEARCH_CACHE.pop(sid, None)


def format_search_card(item: MovieItem, index: int, total: int, query: str) -> str:
    site_emojis = {
        "MLSBD": "🇧🇩",
        "VegaMovies": "⭐",
        "4K-HDHub": "💎",
        "MoviesMod": "⚡",
        "SkyMoviesHD": "☁️",
        "ExtraFlix": "🍿",
        "HDHub4u": "🎯",
        "KatMovieHD": "🦁",
        "KatDrama": "🎭",
        "DotMovies": "🎪",
        "BollyFlix": "🎬",
        "CineVood": "🍿",
        "ToonWorld4All": "🌀",
    }
    emoji = site_emojis.get(item.site, "🎬")
    title = escape(item.clean_title())
    quality = escape(item.quality or "HD")
    site = escape(item.site)
    q_esc = escape(query)

    return (
        "🔍 <b>RDX Premium Movie Search</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 <b>{title}</b>\n\n"
        f"🏷 <b>Source:</b> {emoji} <b>{site}</b>\n"
        f"🎞 <b>Quality:</b> <code>{quality}</code>\n"
        f"🔗 <b>Post Link:</b> <code>{escape(item.url)}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <i>Result {index + 1} of {total} for:</i> <b>\"{q_esc}\"</b>\n"
        "⚡ <i>Select an action below:</i>"
    )


def build_search_keyboard(item: MovieItem, index: int, total: int, search_id: str) -> dict:
    encoded_url = quote(item.url, safe="")
    if LEECH_BOT_USERNAME:
        leech_url = f"https://t.me/{LEECH_BOT_USERNAME}?start={encoded_url}"
    else:
        leech_url = f"https://t.me/share/url?url={encoded_url}"

    kb = [
        [{"text": "🌐 Open Website", "url": item.url}],
        [{"text": "⚡ Send to Leech Bot", "url": leech_url}],
    ]

    nav_row = []
    if index > 0:
        nav_row.append({"text": "◀️ Prev", "callback_data": f"s_nav:{search_id}:{index-1}"})
    nav_row.append({"text": f"📄 {index+1}/{total}", "callback_data": "s_noop"})
    if index < total - 1:
        nav_row.append({"text": "Next ▶️", "callback_data": f"s_nav:{search_id}:{index+1}"})

    kb.append(nav_row)
    kb.append([{"text": "❌ Close", "callback_data": f"s_close:{search_id}"}])
    return {"inline_keyboard": kb}


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
        # Collect 1 sample per site to post as verification greeting
        samples_by_site = {}
        for it in items:
            if it.site not in samples_by_site:
                samples_by_site[it.site] = it
            await db.mark_seen(it.url, it.title, it.site)
        LOGGER.info(
            f"Database initialized with {len(items)} existing movies. Bot is now watching for brand new releases!"
        )

        if BOT_TOKEN and CHANNEL_ID and samples_by_site:
            LOGGER.info(f"Posting 1 sample latest release from each active site ({len(samples_by_site)} sites)...")
            for site_name, sample in samples_by_site.items():
                LOGGER.info(f"Posting initial sample for {site_name}: {sample.title}")
                await post_movie_to_channel(sample)
                await asyncio.sleep(2)

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
    if ENABLE_EXTRAFLIX:
        sources.append("ExtraFlix")
    if ENABLE_HDHUB4U:
        sources.append("HDHub4u")
    if ENABLE_KATMOVIEHD:
        sources.append("KatMovieHD")
    if ENABLE_KATDRAMA:
        sources.append("KatDrama")
    if ENABLE_DOTMOVIES:
        sources.append("DotMovies")
    if ENABLE_BOLLYFLIX:
        sources.append("BollyFlix")
    if ENABLE_CINEVOOD:
        sources.append("CineVood")
    if ENABLE_TOONWORLD:
        sources.append("ToonWorld4All")

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
        f"🔍 <b>Search Engine:</b> Active across all 13 sites\n"
        f"🗄 <b>DB Type:</b> {'MongoDB Atlas' if DATABASE_URL else 'SQLite (Local)'}"
    )


async def generate_sources_text() -> str:
    vega_domain = await resolve_active_vega_domain()
    mm_domain = await resolve_active_moviesmod_domain()
    sky_domain = await resolve_active_domain()
    ef_domain = await resolve_active_extraflix_domain()
    hd_domain = await resolve_active_hdhub4u_domain()
    km_domain = await resolve_active_katmoviehd_domain()
    kd_domain = await resolve_active_katdrama_domain()
    dm_domain = await resolve_active_dotmovies_domain()
    bf_domain = await resolve_active_bollyflix_domain()
    cv_domain = await resolve_active_cinevood_domain()
    tw_domain = await resolve_active_toonworld_domain()

    return (
        "🌐 <b>Active Monitored Sources & Domains</b>\n\n"
        f"🇧🇩 <b>MLSBD:</b> <code>{MLSBD_FEED}</code>\n"
        f"⭐ <b>VegaMovies:</b> <code>{vega_domain}</code>\n"
        f"   └ <i>Auto-resolver: {VEGA_HUB_URL}</i>\n"
        f"💎 <b>4K-HDHub:</b> <code>{FOURKHDHUB_URL}</code>\n"
        f"⚡ <b>MoviesMod:</b> <code>{mm_domain}</code>\n"
        f"   └ <i>Auto-resolver: {MODLIST_HUB_URL}</i>\n"
        f"☁️ <b>SkyMoviesHD:</b> <code>{sky_domain}</code>\n"
        f"   └ <i>Auto-resolver: {SKYBAP_URL}</i>\n"
        f"🍿 <b>ExtraFlix:</b> <code>{ef_domain}</code>\n"
        f"   └ <i>Auto-resolver: {EXTRAFLIX_HUB_URL}</i>\n"
        f"🎯 <b>HDHub4u:</b> <code>{hd_domain}</code>\n"
        f"   └ <i>Auto-resolver: {HDHUB4U_HUB_URL}</i>\n"
        f"🦁 <b>KatMovieHD:</b> <code>{km_domain}</code>\n"
        f"   └ <i>Auto-resolver: {KATMOVIEHD_HUB_URL}</i>\n"
        f"🎭 <b>KatDrama:</b> <code>{kd_domain}</code>\n"
        f"🎪 <b>DotMovies:</b> <code>{dm_domain}</code>\n"
        f"   └ <i>Auto-resolver: {DOTMOVIES_HUB_URL}</i>\n"
        f"🎬 <b>BollyFlix:</b> <code>{bf_domain}</code>\n"
        f"   └ <i>Auto-resolver: {BOLLYFLIX_HUB_URL}</i>\n"
        f"🍿 <b>CineVood:</b> <code>{cv_domain}</code>\n"
        f"   └ <i>Auto-resolver: {CINEVOOD_HUB_URL}</i>\n"
        f"🌀 <b>ToonWorld4All:</b> <code>{tw_domain}</code>\n\n"
        "💡 <i>All domains auto-detect from official hubs, but can also be manually overridden in config!</i>"
    )


_LAST_REBOOT_TIME = 0


async def restart_bot(session: aiohttp.ClientSession, chat_id: int, update_id: Optional[int] = None):
    """Gracefully restart the bot process."""
    global _LAST_REBOOT_TIME
    now = time.time()
    if now - _LAST_REBOOT_TIME < 15:
        LOGGER.warning("Restart command received too soon after previous reboot. Ignoring to prevent loop.")
        return
    _LAST_REBOOT_TIME = now

    # 1. Immediately acknowledge this update with Telegram so it is never re-delivered
    if update_id is not None:
        try:
            ack_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={update_id + 1}&limit=1"
            async with session.get(ack_url, timeout=aiohttp.ClientTimeout(total=5)) as ack_resp:
                await ack_resp.read()
            LOGGER.info(f"Acknowledged restart update {update_id} with Telegram.")
        except Exception as e:
            LOGGER.debug(f"Failed to ack update before restart: {e}")

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

        # Drop any stale unconfirmed backlog on startup so old commands are never re-executed
        try:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1") as resp:
                if resp.status == 200:
                    d = await resp.json()
                    res = d.get("result", [])
                    if res:
                        offset = res[-1]["update_id"] + 1
                        LOGGER.info(f"Initialized Telegram poller offset to {offset} (cleared stale queue).")
        except Exception as e:
            LOGGER.warning(f"Could not clear poller backlog: {e}")

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
                                await restart_bot(session, cb_chat_id, update_id=update["update_id"])
                            elif cb_data.startswith("s_nav:"):
                                parts = cb_data.split(":")
                                if len(parts) == 3:
                                    search_id, target_idx = parts[1], int(parts[2])
                                    s_data = SEARCH_CACHE.get(search_id)
                                    if s_data and 0 <= target_idx < len(s_data["items"]):
                                        item = s_data["items"][target_idx]
                                        caption = format_search_card(item, target_idx, len(s_data["items"]), s_data["query"])
                                        reply_markup = build_search_keyboard(item, target_idx, len(s_data["items"]), search_id)

                                        # Try editMessageCaption first, else editMessageText
                                        edit_cap_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption"
                                        cap_payload = {
                                            "chat_id": cb_chat_id,
                                            "message_id": cb_msg_id,
                                            "caption": caption,
                                            "parse_mode": "HTML",
                                            "reply_markup": reply_markup,
                                        }
                                        async with session.post(edit_cap_url, json=cap_payload) as cap_resp:
                                            if cap_resp.status != 200:
                                                edit_txt_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                                                txt_payload = {
                                                    "chat_id": cb_chat_id,
                                                    "message_id": cb_msg_id,
                                                    "text": caption,
                                                    "parse_mode": "HTML",
                                                    "reply_markup": reply_markup,
                                                }
                                                await session.post(edit_txt_url, json=txt_payload)
                                continue

                            elif cb_data.startswith("s_close:"):
                                parts = cb_data.split(":")
                                if len(parts) == 2:
                                    SEARCH_CACHE.pop(parts[1], None)
                                del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                                await session.post(del_url, json={"chat_id": cb_chat_id, "message_id": cb_msg_id})
                                continue

                            elif cb_data == "s_noop":
                                continue
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
                            await restart_bot(session, chat_id, update_id=update["update_id"])

                        elif text.startswith(("/search", "/s")):
                            clean_search_cache()
                            cmd_parts = text.split(maxsplit=1)
                            if len(cmd_parts) == 1:
                                help_search = (
                                    "🔍 <b>RDX Multi-Platform Movie Search</b>\n\n"
                                    "💡 <b>Usage:</b>\n"
                                    "<code>/search &lt;movie or series name&gt;</code>\n"
                                    "<i>or short alias:</i> <code>/s Avengers</code>\n\n"
                                    "🌐 <b>Supported Platforms:</b>\n"
                                    "• KatMovieHD (4K UHD) • KatDrama (K-Drama & Asian)\n"
                                    "• DotMovies • BollyFlix (Bollywood & Dual Audio)\n"
                                    "• CineVood / FilmyZilla • ToonWorld4All (Anime)\n"
                                    "• VegaMovies • MoviesMod • ExtraFlix • HDHub4u\n"
                                    "• MLSBD • 4K-HDHub • SkyMoviesHD\n\n"
                                    "⚡ <i>Instant interactive cards with direct Leech Bot launch!</i>"
                                )
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": chat_id, "text": help_search, "parse_mode": "HTML"},
                                )
                                continue

                            query = cmd_parts[1].strip()
                            wait_msg_id = None
                            try:
                                wait_res = await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={
                                        "chat_id": chat_id,
                                        "text": f"🔍 <i>Searching across all platforms for</i> <b>\"{escape(query)}\"</b>...",
                                        "parse_mode": "HTML",
                                    },
                                )
                                wait_data = await wait_res.json()
                                if wait_data.get("ok"):
                                    wait_msg_id = wait_data["result"]["message_id"]
                            except Exception:
                                pass

                            items = await search_all_sites(query, max_total=24)

                            if wait_msg_id:
                                try:
                                    await session.post(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                                        json={"chat_id": chat_id, "message_id": wait_msg_id},
                                    )
                                except Exception:
                                    pass

                            if not items:
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={
                                        "chat_id": chat_id,
                                        "text": f"❌ <b>No results found for:</b> <i>\"{escape(query)}\"</i>\n💡 <i>Try searching with a shorter title or different spelling!</i>",
                                        "parse_mode": "HTML",
                                    },
                                )
                                continue

                            search_id = str(uuid.uuid4())[:8]
                            SEARCH_CACHE[search_id] = {"query": query, "items": items, "ts": time.time()}

                            first_item = items[0]
                            caption = format_search_card(first_item, 0, len(items), query)
                            reply_markup = build_search_keyboard(first_item, 0, len(items), search_id)

                            posted = False
                            if first_item.poster:
                                photo_payload = {
                                    "chat_id": chat_id,
                                    "photo": first_item.poster,
                                    "caption": caption,
                                    "parse_mode": "HTML",
                                    "reply_markup": reply_markup,
                                }
                                try:
                                    async with session.post(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                                        json=photo_payload,
                                    ) as p_resp:
                                        p_data = await p_resp.json()
                                        if p_data.get("ok"):
                                            posted = True
                                except Exception:
                                    posted = False

                            if not posted:
                                msg_payload = {
                                    "chat_id": chat_id,
                                    "text": caption,
                                    "parse_mode": "HTML",
                                    "reply_markup": reply_markup,
                                }
                                await session.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json=msg_payload,
                                )
                            continue

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
