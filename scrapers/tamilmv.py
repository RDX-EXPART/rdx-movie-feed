import asyncio
import logging
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

import config
TAMILMV_URL = getattr(config, "TAMILMV_URL", None)
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("Scraper1TamilMV")

_CACHED_TMV_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_TMV: float = 0
CACHE_TTL = 3600

DEFAULT_TAMILMV_URL = "https://www.1tamilmv.fi"
FALLBACK_MIRRORS = [
    "https://www.1tamilmv.fi",
    "https://www.1tamilmv.ceo",
    "https://www.1tamilmv.re",
    "https://www.1tamilmv.lat",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(
        r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|8[kK]|HEVC|AVC|HDR|HDR10|DV|Dolby|DDP?5\.1|TRUE\s*WEB-DL|WEB-DL|BluRay|REMUX)\b",
        text,
        re.I,
    )
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


def _fetch_tmv_page(url: str, timeout: int = 15) -> tuple[str, str]:
    """Fetch 1TamilMV page using curl_cffi or requests."""
    try:
        from curl_cffi import requests as cffi_requests
        for imp in ("chrome120", "chrome110", "chrome119"):
            try:
                r = cffi_requests.get(url, impersonate=imp, allow_redirects=True, timeout=timeout)
                if r.status_code == 200 and len(r.text) > 300:
                    return r.text, str(r.url).rstrip("/")
            except Exception:
                continue
    except Exception as e:
        LOGGER.debug(f"curl_cffi get error for {url}: {e}")

    try:
        import requests
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 300:
            return r.text, str(r.url).rstrip("/")
    except Exception:
        pass

    return "", url


async def resolve_active_tamilmv_domain() -> str:
    global _CACHED_TMV_DOMAIN, _CACHE_EXPIRE_TMV

    now = time.time()
    if _CACHED_TMV_DOMAIN and now < _CACHE_EXPIRE_TMV:
        return _CACHED_TMV_DOMAIN

    loop = asyncio.get_running_loop()
    for mirror in FALLBACK_MIRRORS:
        html, final_url = await loop.run_in_executor(None, _fetch_tmv_page, mirror, 10)
        if html:
            LOGGER.info(f"Auto-detected working 1TamilMV domain: {final_url}")
            _CACHED_TMV_DOMAIN = final_url
            _CACHE_EXPIRE_TMV = now + CACHE_TTL
            return final_url

    return DEFAULT_TAMILMV_URL


async def scrape_tamilmv() -> List[MovieItem]:
    """Scrape latest torrent releases from 1TamilMV homepage."""
    base_url = await resolve_active_tamilmv_domain()
    LOGGER.info(f"Fetching 1TamilMV releases from {base_url}...")

    loop = asyncio.get_running_loop()
    html, final_url = await loop.run_in_executor(None, _fetch_tmv_page, base_url, 15)
    if not html:
        LOGGER.warning(f"Failed to fetch 1TamilMV HTML from {base_url}.")
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        topics = soup.select('div.ipsType_break a[href*="/topic/"]')
        for a in topics:
            href = a.get("href")
            if not href or href in seen:
                continue
            seen.add(href)

            raw_title = a.get_text(" ", strip=True)
            clean_title = re.sub(r"^www\.[a-zA-Z0-9\.\-]+\s*-\s*", "", raw_title, flags=re.I).strip()
            if not clean_title or len(clean_title) < 5 or clean_title.lower().startswith(("rules", "notice", "announcement")):
                continue

            quality = extract_qualities(clean_title)
            items.append(
                MovieItem(
                    site="1TamilMV",
                    title=clean_title,
                    url=href,
                    poster=None,
                    quality=quality,
                )
            )
    except Exception as e:
        LOGGER.error(f"Error parsing 1TamilMV: {e}")

    LOGGER.info(f"1TamilMV scraper found {len(items)} items.")
    return items


async def search_tamilmv(query: str, limit: int = 6) -> List[MovieItem]:
    """Search 1TamilMV forum topics."""
    base_url = await resolve_active_tamilmv_domain()
    search_url = f"{base_url}/index.php?/search/&q={quote_plus(query)}&type=forums_topic"

    loop = asyncio.get_running_loop()
    html, _ = await loop.run_in_executor(None, _fetch_tmv_page, search_url, 15)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "/topic/" not in href or not a.get_text(strip=True):
                continue

            txt = a.get_text(" ", strip=True)
            if any(ign in txt.lower() for ign in ["languages", "reply", "replies", "rules", "how to"]):
                continue

            clean_url = href.split("&do=findComment")[0].split("?do=findComment")[0]
            if clean_url in seen:
                continue
            seen.add(clean_url)

            clean_title = re.sub(r"^www\.[a-zA-Z0-9\.\-]+\s*-\s*", "", txt, flags=re.I).strip()
            if len(clean_title) > 5:
                items.append(
                    MovieItem(
                        site="1TamilMV",
                        title=clean_title,
                        url=clean_url,
                        poster=None,
                        quality=extract_qualities(clean_title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"1TamilMV search error: {e}")
    return items
