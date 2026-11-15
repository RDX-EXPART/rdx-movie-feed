import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import FILMYCAB_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperFilmyCab")

_CACHED_FC_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_FC: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://filmycab.surf",
    "https://filmycab.pw",
    "https://filmycab.org",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(
        r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|DS4K|HEVC|HDR|WEB-DL|BluRay|PreDVDRip|HDRip|HDTC|ESub)\b",
        text,
        re.I,
    )
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_filmycab_domain() -> str:
    global _CACHED_FC_DOMAIN, _CACHE_EXPIRE_FC

    if FILMYCAB_URL:
        return FILMYCAB_URL

    now = time.time()
    if _CACHED_FC_DOMAIN and now < _CACHE_EXPIRE_FC:
        return _CACHED_FC_DOMAIN

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working mirror for FilmyCab: {mirror}")
            _CACHED_FC_DOMAIN = mirror
            _CACHE_EXPIRE_FC = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_filmycab() -> List[MovieItem]:
    """Scrape latest releases from FilmyCab."""
    base_url = await resolve_active_filmycab_domain()
    LOGGER.info(f"Fetching FilmyCab releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch FilmyCab HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        thumbs = soup.select("div.thumb, div.rsz, figure, section.thumbnail-wrapper div.thumb")
        if not thumbs:
            thumbs = soup.find_all("figure")

        for thumb in thumbs:
            a = thumb.find("a", href=lambda h: h and h.endswith(".html"))
            if not a or not a.get("href"):
                continue

            url = urljoin(base_url, a["href"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img = thumb.find("img")
            title = ""
            poster = None
            if img:
                title = img.get("alt", "").strip()
                poster = img.get("src") or img.get("data-src")
                if poster:
                    poster = urljoin(base_url, poster)

            if not title:
                title = a.get_text(" ", strip=True)
                title = re.sub(r"^(?:Download|Watch)\s*", "", title, flags=re.I).strip()

            if not title:
                # Fallback to slug in url
                slug = a["href"].rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ")
                title = slug

            quality = extract_qualities(title)

            items.append(
                MovieItem(
                    site="FilmyCab",
                    title=title,
                    url=url,
                    poster=poster,
                    quality=quality,
                )
            )
    except Exception as e:
        LOGGER.error(f"Error parsing FilmyCab releases: {e}")

    LOGGER.info(f"Successfully scraped {len(items)} items from FilmyCab.")
    return items
