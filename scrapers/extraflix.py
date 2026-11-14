import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import EXTRAFLIX_HUB_URL, EXTRAFLIX_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperExtraFlix")

_CACHED_EXTRAFLIX_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_EF: float = 0
CACHE_TTL = 3600  # 1 hour cache

FALLBACK_MIRRORS = [
    "https://e14.extraflix.mobi",
    "https://e15.extraflix.mobi",
    "https://e13.extraflix.mobi",
    "https://extraflix.mobi",
    "https://extraflix.pw",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|HDRip|WEB-DL|Blu-?Ray)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_extraflix_domain() -> str:
    """Auto-detect the latest active ExtraFlix domain via extraflix.foo or user config."""
    global _CACHED_EXTRAFLIX_DOMAIN, _CACHE_EXPIRE_EF

    # 1. Manual override from config
    if EXTRAFLIX_URL:
        return EXTRAFLIX_URL

    # 2. In-memory cache
    now = time.time()
    if _CACHED_EXTRAFLIX_DOMAIN and now < _CACHE_EXPIRE_EF:
        return _CACHED_EXTRAFLIX_DOMAIN

    LOGGER.info(f"Auto-detecting active ExtraFlix domain from hub {EXTRAFLIX_HUB_URL}...")
    try:
        html = await fetch_html(EXTRAFLIX_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            # Match extraflix domains from links or scripts
            m = re.findall(r"https?://(?:[a-zA-Z0-9\-]+\.)?extraflix\.[a-z0-9]+", html, re.I)
            if m:
                # Prefer mirror with subdomain/tld other than .foo
                candidates = [u.rstrip("/") for u in m if not u.endswith(".foo")]
                if candidates:
                    detected = candidates[0]
                    LOGGER.info(f"Auto-detected ExtraFlix domain from hub: {detected}")
                    _CACHED_EXTRAFLIX_DOMAIN = detected
                    _CACHE_EXPIRE_EF = now + CACHE_TTL
                    return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect ExtraFlix domain from hub: {e}")

    # 3. Test fallback mirrors
    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for ExtraFlix: {mirror}")
            _CACHED_EXTRAFLIX_DOMAIN = mirror
            _CACHE_EXPIRE_EF = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_extraflix() -> List[MovieItem]:
    """Scrape latest items from ExtraFlix."""
    base_url = await resolve_active_extraflix_domain()
    LOGGER.info(f"Fetching ExtraFlix releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch ExtraFlix HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article.entry-card, article.post, div.post")
        if not articles:
            articles = soup.find_all("article")

        for article in articles:
            a = article.find("a")
            if not a or not a.get("href"):
                continue

            href = a["href"].strip()
            url = urljoin(base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Skip non-post pages
            if any(x in url for x in ("/category/", "/genre/", "/tag/", "/page/", "/author/")):
                continue

            img = article.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster and not poster.startswith("http"):
                    poster = urljoin(base_url, poster)

            title_el = article.find(["h2", "h3", "h4", ".entry-title"])
            title = ""
            if title_el:
                title = title_el.get_text(strip=True)
            elif a.get("aria-label"):
                title = a["aria-label"].strip()
            elif img and img.get("alt"):
                title = img["alt"].strip()
            else:
                title = a.get_text(strip=True)

            # Clean leading/trailing junk
            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()

            if title and url and len(title) > 5:
                items.append(
                    MovieItem(
                        site="ExtraFlix",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing ExtraFlix: {e}")

    LOGGER.info(f"ExtraFlix scraper found {len(items)} items.")
    return items
