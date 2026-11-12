import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import DOTMOVIES_HUB_URL, DOTMOVIES_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperDotMovies")

_CACHED_DM_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_DM: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://dotmoviess.co.in",
    "https://dotmovies.army",
    "https://dotmovies.lat",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL|BluRay|PreDVDRip|HDRip)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_dotmovies_domain() -> str:
    global _CACHED_DM_DOMAIN, _CACHE_EXPIRE_DM

    if DOTMOVIES_URL:
        return DOTMOVIES_URL

    now = time.time()
    if _CACHED_DM_DOMAIN and now < _CACHE_EXPIRE_DM:
        return _CACHED_DM_DOMAIN

    LOGGER.info(f"Auto-detecting DotMovies domain from hub {DOTMOVIES_HUB_URL}...")
    try:
        html = await fetch_html(DOTMOVIES_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            m = re.findall(r'https?://(?:[a-zA-Z0-9\-]+\.)?dotmovies[a-z0-9\.\-]+', html, re.I)
            if m:
                detected = m[0].rstrip("/")
                LOGGER.info(f"Auto-detected DotMovies domain: {detected}")
                _CACHED_DM_DOMAIN = detected
                _CACHE_EXPIRE_DM = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect DotMovies domain: {e}")

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for DotMovies: {mirror}")
            _CACHED_DM_DOMAIN = mirror
            _CACHE_EXPIRE_DM = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_dotmovies() -> List[MovieItem]:
    """Scrape latest movies and series from DotMovies."""
    base_url = await resolve_active_dotmovies_domain()
    LOGGER.info(f"Fetching DotMovies releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch DotMovies HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item, .story-item")
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

            heading = p.select_one("h1, h2, h3, .entry-title, .title, .story-title")
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
                        site="DotMovies",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing DotMovies: {e}")

    LOGGER.info(f"DotMovies scraper found {len(items)} items.")
    return items
