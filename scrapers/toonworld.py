import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import TOONWORLD_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperToonWorld")

_CACHED_TW_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_TW: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://toonworld4all.me",
    "https://www.toonworld4all.me",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL|BluRay|HD)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_toonworld_domain() -> str:
    global _CACHED_TW_DOMAIN, _CACHE_EXPIRE_TW

    if TOONWORLD_URL:
        return TOONWORLD_URL

    now = time.time()
    if _CACHED_TW_DOMAIN and now < _CACHE_EXPIRE_TW:
        return _CACHED_TW_DOMAIN

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working mirror for ToonWorld: {mirror}")
            _CACHED_TW_DOMAIN = mirror
            _CACHE_EXPIRE_TW = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_toonworld() -> List[MovieItem]:
    """Scrape latest anime and cartoon series from ToonWorld4All."""
    base_url = await resolve_active_toonworld_domain()
    LOGGER.info(f"Fetching ToonWorld releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch ToonWorld HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
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

            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()

            if (
                title
                and url
                and len(title) > 5
                and not url.endswith("#")
                and url.rstrip("/") != base_url.rstrip("/")
                and not any(x in url for x in ("/category/", "/tag/", "/page/", "/cdn-cgi/"))
            ):
                items.append(
                    MovieItem(
                        site="ToonWorld4All",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing ToonWorld: {e}")

    LOGGER.info(f"ToonWorld scraper found {len(items)} items.")
    return items
