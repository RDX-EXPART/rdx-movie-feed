import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import BOLLYFLIX_HUB_URL, BOLLYFLIX_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperBollyFlix")

_CACHED_BF_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_BF: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://bollyflix.church",
    "https://bollyflix.deal",
    "https://bollyflix.baby",
    "https://bollyflix.nz",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL|BluRay|PreDVDRip|HDRip)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_bollyflix_domain() -> str:
    global _CACHED_BF_DOMAIN, _CACHE_EXPIRE_BF

    if BOLLYFLIX_URL:
        return BOLLYFLIX_URL

    now = time.time()
    if _CACHED_BF_DOMAIN and now < _CACHE_EXPIRE_BF:
        return _CACHED_BF_DOMAIN

    LOGGER.info(f"Auto-detecting BollyFlix domain from hub {BOLLYFLIX_HUB_URL}...")
    try:
        html = await fetch_html(BOLLYFLIX_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            m = re.findall(r'https?://(?:[a-zA-Z0-9\-]+\.)?bollyflix\.[a-z0-9]+/?', html, re.I)
            if m:
                detected = m[0].rstrip("/")
                LOGGER.info(f"Auto-detected BollyFlix domain: {detected}")
                _CACHED_BF_DOMAIN = detected
                _CACHE_EXPIRE_BF = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect BollyFlix domain: {e}")

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for BollyFlix: {mirror}")
            _CACHED_BF_DOMAIN = mirror
            _CACHE_EXPIRE_BF = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_bollyflix() -> List[MovieItem]:
    """Scrape latest items from BollyFlix."""
    base_url = await resolve_active_bollyflix_domain()
    LOGGER.info(f"Fetching BollyFlix releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch BollyFlix HTML from {base_url}.")
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

            if title and url and len(title) > 5 and not url.endswith(("#", "/")):
                items.append(
                    MovieItem(
                        site="BollyFlix",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing BollyFlix: {e}")

    LOGGER.info(f"BollyFlix scraper found {len(items)} items.")
    return items
