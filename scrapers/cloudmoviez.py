import asyncio
import logging
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperCloudMoviez")

_CACHED_CM_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_CM: float = 0
CACHE_TTL = 3600

DEFAULT_CLOUDMOVIEZ_URL = "https://cloudmoviez.space"
FALLBACK_MIRRORS = [
    "https://cloudmoviez.space",
    "https://c2.cloudmoviez.space",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(
        r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|H\.?264|H\.?265|HEVC|WEB-DL|AMZN|HDR|DV|Dual\s*Audio)\b",
        text,
        re.I,
    )
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


def _clean_post_title(title: str) -> str:
    title = re.sub(r"^download\s+", "", title, flags=re.I).strip()
    return " ".join(title.split())


async def resolve_active_cloudmoviez_domain() -> str:
    global _CACHED_CM_DOMAIN, _CACHE_EXPIRE_CM

    cm_url = getattr(config, "CLOUDMOVIEZ_URL", None)
    if cm_url:
        return cm_url.rstrip("/")

    now = time.time()
    if _CACHED_CM_DOMAIN and now < _CACHE_EXPIRE_CM:
        return _CACHED_CM_DOMAIN

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=8)
        if test_html:
            LOGGER.info(f"Auto-detected working CloudMoviez domain: {mirror}")
            _CACHED_CM_DOMAIN = mirror
            _CACHE_EXPIRE_CM = now + CACHE_TTL
            return mirror

    return DEFAULT_CLOUDMOVIEZ_URL


async def scrape_cloudmoviez() -> List[MovieItem]:
    """Scrape latest items from CloudMoviez."""
    base_url = await resolve_active_cloudmoviez_domain()
    LOGGER.info(f"Fetching CloudMoviez releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch CloudMoviez HTML from {base_url}.")
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article, div.post, .post-item, .card, div.latest-post, .item, a[href*='/tvshows/'], a[href*='/movies/']")
        for card in cards:
            a = card if card.name == "a" else card.find("a")
            if not a or not a.get("href"):
                continue

            href = a["href"].strip()
            url = urljoin(base_url, href)
            if (
                url in seen
                or url.endswith("#")
                or url.rstrip("/") == base_url.rstrip("/")
                or any(x in url for x in ("/category/", "/tag/", "/page/"))
            ):
                continue
            seen.add(url)

            img = card.find("img") if card.name != "a" else a.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = card.select_one("h1, h2, h3, .entry-title, .title, .card-title") if card.name != "a" else None
            title = heading.get_text(strip=True) if heading else (img.get("alt") if img and img.get("alt") else a.get_text(strip=True))
            title = _clean_post_title(title)

            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="CloudMoviez",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing CloudMoviez: {e}")

    LOGGER.info(f"CloudMoviez scraper found {len(items)} items.")
    return items


async def search_cloudmoviez(query: str, limit: int = 6) -> List[MovieItem]:
    """Search CloudMoviez for movies and series."""
    base_url = await resolve_active_cloudmoviez_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=12)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article, div.post, .post-item, .card, div.latest-post, .item, a[href*='/tvshows/'], a[href*='/movies/']")
        for card in cards:
            a = card if card.name == "a" else card.find("a")
            if not a or not a.get("href"):
                continue

            url = urljoin(base_url, a["href"])
            if (
                url in seen
                or url.endswith("#")
                or url.rstrip("/") == base_url.rstrip("/")
                or any(x in url for x in ("/category/", "/tag/", "/page/"))
            ):
                continue
            seen.add(url)

            img = card.find("img") if card.name != "a" else a.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = card.select_one("h1, h2, h3, .entry-title, .title, .card-title") if card.name != "a" else None
            title = heading.get_text(strip=True) if heading else (img.get("alt") if img and img.get("alt") else a.get_text(strip=True))
            title = _clean_post_title(title)

            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="CloudMoviez",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"CloudMoviez search error: {e}")
    return items
