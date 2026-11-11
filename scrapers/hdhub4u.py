import base64
import json
import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import HDHUB4U_HUB_URL, HDHUB4U_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperHDHub4u")

_CACHED_HDHUB4U_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_HD: float = 0
CACHE_TTL = 3600  # 1 hour cache

# Official HDHub4u host API endpoints used by hdhub4u.deal
HOST_APIS = [
    "https://h4.suncdn.org/host/",
    "https://points.topapii.com/host/",
    "https://ml.theapii.org/host/",
    "https://cdn.hub4u.cloud/host/",
]

FALLBACK_MIRRORS = [
    "https://new12.hdhub4u.cl",
    "https://hdhub4u.cl",
    "https://hdhub4u.ms",
    "https://hdhub4u.download",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|10[bB]it|HDR|HDRip|WEB-DL|Blu-?Ray|HQ-HDTC|HDTC)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_hdhub4u_domain() -> str:
    """Auto-detect the latest active HDHub4u domain via host API, hub or user config."""
    global _CACHED_HDHUB4U_DOMAIN, _CACHE_EXPIRE_HD

    # 1. Manual override from config
    if HDHUB4U_URL:
        return HDHUB4U_URL

    # 2. In-memory cache
    now = time.time()
    if _CACHED_HDHUB4U_DOMAIN and now < _CACHE_EXPIRE_HD:
        return _CACHED_HDHUB4U_DOMAIN

    LOGGER.info(f"Auto-detecting active HDHub4u domain from host APIs...")
    # 3. Query official host APIs (returns base64-encoded active target)
    for api_url in HOST_APIS:
        try:
            raw_json = await fetch_html(api_url, timeout=5, use_jina_fallback=False)
            if raw_json:
                data = json.loads(raw_json)
                if isinstance(data, dict) and "c" in data:
                    decoded = base64.b64decode(data["c"]).decode("utf-8", "ignore").strip()
                    # Strip ?utm=... parameters
                    detected = decoded.split("?")[0].rstrip("/")
                    if detected.startswith("http"):
                        LOGGER.info(f"Auto-detected HDHub4u domain from API {api_url}: {detected}")
                        _CACHED_HDHUB4U_DOMAIN = detected
                        _CACHE_EXPIRE_HD = now + CACHE_TTL
                        return detected
        except Exception as e:
            LOGGER.debug(f"Host API {api_url} check error: {e}")

    # 4. Hub fallback
    try:
        html = await fetch_html(HDHUB4U_HUB_URL, timeout=6, use_jina_fallback=False)
        if html:
            m = re.search(r"url=[\"\'](https?://[^\"\']+)[\"\']", html, re.I)
            if m:
                detected = m.group(1).split("?")[0].rstrip("/")
                LOGGER.info(f"Auto-detected HDHub4u domain from hub {HDHUB4U_HUB_URL}: {detected}")
                _CACHED_HDHUB4U_DOMAIN = detected
                _CACHE_EXPIRE_HD = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to query HDHub4u hub: {e}")

    # 5. Test fallback mirrors
    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for HDHub4u: {mirror}")
            _CACHED_HDHUB4U_DOMAIN = mirror
            _CACHE_EXPIRE_HD = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def scrape_hdhub4u() -> List[MovieItem]:
    """Scrape latest items from HDHub4u."""
    base_url = await resolve_active_hdhub4u_domain()
    LOGGER.info(f"Fetching HDHub4u releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch HDHub4u HTML from {base_url}.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        # HDHub4u uses li.thumb with figure and a
        cards = soup.select("li.thumb, li.recent-posts, article, div.post")
        if not cards:
            for li in soup.find_all("li"):
                if li.find("figure") or (li.find("img") and li.find("a")):
                    cards.append(li)

        for card in cards:
            a = card.find("a")
            if not a or not a.get("href"):
                continue

            href = a["href"].strip()
            url = urljoin(base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Skip header/footer links
            if any(x in url for x in ("/category/", "/genre/", "/tag/", "/how-to-download", "/join-our-group", "/disclaimer")):
                continue

            img = card.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster and not poster.startswith("http"):
                    poster = urljoin(base_url, poster)

            title = ""
            if a.get("aria-label"):
                title = a["aria-label"].strip()
            elif img and img.get("alt"):
                title = img["alt"].strip()
            else:
                title = card.get_text(" ", strip=True)

            # Strip leading/trailing junk
            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()
            title = re.sub(r"\s*\|\s*Full\s+Movie.*$", "", title, flags=re.I).strip()

            if title and url and len(title) > 5 and ("202" in title or "201" in title or "19" in title or "season" in title.lower()):
                items.append(
                    MovieItem(
                        site="HDHub4u",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing HDHub4u: {e}")

    LOGGER.info(f"HDHub4u scraper found {len(items)} items.")
    return items
