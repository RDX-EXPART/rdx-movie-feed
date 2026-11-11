import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import MODLIST_HUB_URL, MOVIESMOD_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperMoviesMod")

_CACHED_MM_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_MM: float = 0
CACHE_TTL = 3600  # 1 hour cache

FALLBACK_MIRRORS = [
    "https://moviesmod.tw",
    "https://moviesmod.at",
    "https://moviesmod.gd",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_moviesmod_domain() -> str:
    """Auto-detect the latest MoviesMod domain via modlist.in or user config."""
    global _CACHED_MM_DOMAIN, _CACHE_EXPIRE_MM

    # 1. Manual override from config
    if MOVIESMOD_URL:
        return MOVIESMOD_URL

    # 2. In-memory cache
    now = time.time()
    if _CACHED_MM_DOMAIN and now < _CACHE_EXPIRE_MM:
        return _CACHED_MM_DOMAIN

    LOGGER.info(f"Auto-detecting active MoviesMod domain from hub {MODLIST_HUB_URL}...")
    try:
        html = await fetch_html(MODLIST_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            # Check meta refresh or redirect message
            m = re.search(r"url=(https?://[^\s\"\'\>]+)", html, re.I)
            if not m:
                m = re.search(r"Redirecting to\s+(https?://[^\s\"\'\<]+)", html, re.I)
            if m:
                detected = m.group(1).rstrip("/")
                LOGGER.info(f"Auto-detected MoviesMod domain from hub: {detected}")
                _CACHED_MM_DOMAIN = detected
                _CACHE_EXPIRE_MM = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect MoviesMod domain: {e}")

    # 3. Test fallback mirrors
    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for MoviesMod: {mirror}")
            _CACHED_MM_DOMAIN = mirror
            _CACHE_EXPIRE_MM = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_moviesmod() -> List[MovieItem]:
    """Scrape latest items from MoviesMod with dynamic domain detection."""
    base_url = await resolve_active_moviesmod_domain()
    LOGGER.info(f"Fetching MoviesMod releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch MoviesMod HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = ""
            if heading:
                title = heading.get_text(strip=True)
            elif a.get("title"):
                title = a["title"].strip()
            elif img and img.get("alt"):
                title = img["alt"].strip()
            else:
                title = a.get_text(strip=True)

            # Strip redundant words like "Download " from start
            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()

            if title and url and len(title) > 5:
                items.append(
                    MovieItem(
                        site="MoviesMod",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing MoviesMod: {e}")

    LOGGER.info(f"MoviesMod scraper found {len(items)} items.")
    return items
