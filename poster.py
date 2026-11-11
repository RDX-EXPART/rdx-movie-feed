import asyncio
import json
import logging
from html import escape
from typing import Optional
from urllib.parse import quote

import aiohttp

from config import BOT_TOKEN, CHANNEL_ID, LEECH_BOTS
from scrapers.base import MovieItem
from scrapers.mlsbd import fetch_mlsbd_poster

LOGGER = logging.getLogger("Poster")
TELEGRAM_API_URL = "https://api.telegram.org"


def format_caption(item: MovieItem) -> str:
    """Format rich HTML message caption for Telegram."""
    site_emojis = {
        "MLSBD": "🇧🇩",
        "VegaMovies": "⭐",
        "4K-HDHub": "💎",
        "MoviesMod": "⚡",
        "SkyMoviesHD": "☁️",
        "ExtraFlix": "🍿",
        "HDHub4u": "🎯",
    }
    emoji = site_emojis.get(item.site, "🎬")
    title = escape(item.clean_title())
    quality = escape(item.quality or "HD")
    site = escape(item.site)

    lines = [
        f"🎬 <b>{title}</b>",
        "",
        f"🏷 <b>Source:</b> {emoji} <b>{site}</b>",
        f"🎞 <b>Quality:</b> <code>{quality}</code>",
    ]
    if item.date:
        lines.append(f"📅 <b>Date:</b> {escape(item.date)}")
    lines.append("")
    lines.append(f"🔗 <b>Post Link:</b> <code>{escape(item.url)}</code>")
    lines.append("")
    lines.append("⚡ <i>Powered by RDX Movie Feed</i>")
    return "\n".join(lines)


def build_keyboard(item: MovieItem) -> dict:
    """Construct inline keyboard with exactly two stacked buttons: Open Website and Send to Leech Bot."""
    encoded_url = quote(item.url, safe="")
    share_url = f"https://t.me/share/url?url={encoded_url}"
    return {
        "inline_keyboard": [
            [{"text": "🌐 Open Website", "url": item.url}],
            [{"text": "🚀 Send to Leech Bot", "url": share_url}],
        ]
    }


async def post_movie_to_channel(item: MovieItem) -> bool:
    """Post movie card to Telegram Channel using Telegram Bot API."""
    if not BOT_TOKEN or not CHANNEL_ID:
        LOGGER.warning("BOT_TOKEN or CHANNEL_ID is not configured. Skipping channel post.")
        return False

    caption = format_caption(item)
    reply_markup = json.dumps(build_keyboard(item))

    # If MLSBD item has no poster, attempt to fetch it now
    if item.site == "MLSBD" and not item.poster:
        try:
            item.poster = await fetch_mlsbd_poster(item.url)
        except Exception as e:
            LOGGER.debug(f"MLSBD poster fetch error: {e}")

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 1. Try sending photo if poster image URL is present
        if item.poster:
            photo_url = f"{TELEGRAM_API_URL}/bot{BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": CHANNEL_ID,
                "photo": item.poster,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            }
            try:
                async with session.post(photo_url, json=payload) as resp:
                    res_json = await resp.json()
                    if resp.status == 200 and res_json.get("ok"):
                        LOGGER.info(f"Successfully posted photo for: {item.title[:40]} [{item.site}]")
                        return True
                    else:
                        LOGGER.warning(
                            f"sendPhoto failed ({res_json.get('description')}). Falling back to sendMessage..."
                        )
            except Exception as pe:
                LOGGER.warning(f"sendPhoto exception: {pe}. Falling back to sendMessage...")

        # 2. Fallback to sendMessage (text-only or web-preview)
        msg_url = f"{TELEGRAM_API_URL}/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
            "disable_web_page_preview": False,
        }
        try:
            async with session.post(msg_url, json=payload) as resp:
                res_json = await resp.json()
                if resp.status == 200 and res_json.get("ok"):
                    LOGGER.info(f"Successfully posted text for: {item.title[:40]} [{item.site}]")
                    return True
                else:
                    LOGGER.error(f"sendMessage failed: {res_json.get('description')}")
        except Exception as me:
            LOGGER.error(f"sendMessage exception: {me}")

    return False
