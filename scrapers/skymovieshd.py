import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import SKYBAP_URL, SKYMOVIES_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperSkyMovies")

_CACHED_DOMAIN: Optional[str] = None
_CACHE_EXPIRE: float = 0
CACHE_TTL = 3600  # Re-check active domain every 1 hour

FALLBACK_MIRRORS = [
    "https://new4.skymovieshd.clinic",
    "https://skymovieshd.green",
    "https://skymovieshd.in",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|HDRip|DS4K|WEB-DL)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_domain() -> str:
    """Auto-detect the latest SkyMoviesHD domain via SkyBap or user config."""
    global _CACHED_DOMAIN, _CACHE_EXPIRE

    # 1. If manual override is configured by user, use it directly
    if SKYMOVIES_URL:
        return SKYMOVIES_URL

    # 2. Return cached domain if still fresh
    now = time.time()
    if _CACHED_DOMAIN and now < _CACHE_EXPIRE:
        return _CACHED_DOMAIN

    LOGGER.info(f"Auto-detecting active SkyMoviesHD domain from {SKYBAP_URL}...")
    try:
        html = await fetch_html(SKYBAP_URL, timeout=8, use_jina_fallback=False)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            # Look for link containing skymovieshd
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if "skymovieshd" in href.lower() and href.startswith("http"):
                    detected = href.rstrip("/")
                    LOGGER.info(f"Auto-detected SkyMoviesHD domain from SkyBap: {detected}")
                    _CACHED_DOMAIN = detected
                    _CACHE_EXPIRE = now + CACHE_TTL
                    return detected

            # Regex search in raw HTML text
            m = re.search(r"https?://[a-zA-Z0-9\.\-]*skymovieshd\.[a-zA-Z0-9\.\-]+", html, re.I)
            if m:
                detected = m.group(0).rstrip("/")
                LOGGER.info(f"Auto-detected SkyMoviesHD domain via regex: {detected}")
                _CACHED_DOMAIN = detected
                _CACHE_EXPIRE = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect from SkyBap: {e}")

    # 3. Fallback to known mirrors
    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for SkyMoviesHD: {mirror}")
            _CACHED_DOMAIN = mirror
            _CACHE_EXPIRE = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_skymovieshd() -> List[MovieItem]:
    """Scrape latest items from SkyMoviesHD."""
    base_url = await resolve_active_domain()
    LOGGER.info(f"Fetching SkyMoviesHD releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch SkyMoviesHD HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Target movie release links (matching movie/<title>.html or /movie/<title>.html)
        links = soup.find_all("a", href=re.compile(r"(?:^|/)movie/(?!index|\.html)[^/]+\.html", re.I))
        for a in links:
            href = a.get("href", "")
            url = urljoin(base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img = a.find("img")
            poster = None
            if img:
                poster = (
                    img.get("data-src")
                    or img.get("src")
                    or img.get("data-lazy-src")
                )
                if poster and poster.startswith("data:"):
                    poster = None
                if poster:
                    poster = urljoin(base_url, poster)

            title = a.get_text(strip=True)
            if not title and img and img.get("alt"):
                title = img["alt"].strip()

            if title and url and len(title) > 5:
                items.append(
                    MovieItem(
                        site="SkyMoviesHD",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing SkyMoviesHD: {e}")

    LOGGER.info(f"SkyMoviesHD scraper found {len(items)} items.")
    return items
