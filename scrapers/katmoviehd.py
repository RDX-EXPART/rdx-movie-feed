import json
import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import KATMOVIEHD_HUB_URL, KATMOVIEHD_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperKatMovieHD")

_CACHED_KM_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_KM: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://new2.katmoviehd.top",
    "https://katmoviehd.fans",
    "https://katmoviehd.pictures",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|UHD|HEVC|HDR|WEB-DL|BluRay)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_katmoviehd_domain() -> str:
    """Auto-detect the latest KatMovieHD domain via landing hub or config."""
    global _CACHED_KM_DOMAIN, _CACHE_EXPIRE_KM

    if KATMOVIEHD_URL:
        return KATMOVIEHD_URL

    now = time.time()
    if _CACHED_KM_DOMAIN and now < _CACHE_EXPIRE_KM:
        return _CACHED_KM_DOMAIN

    LOGGER.info(f"Auto-detecting active KatMovieHD domain from hub {KATMOVIEHD_HUB_URL}...")
    try:
        html = await fetch_html(KATMOVIEHD_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            m = re.findall(r'https?://(?:[a-zA-Z0-9\-]+\.)?katmoviehd\.[a-z0-9]+/?', html, re.I)
            if m:
                detected = m[0].rstrip("/")
                LOGGER.info(f"Auto-detected KatMovieHD domain from hub: {detected}")
                _CACHED_KM_DOMAIN = detected
                _CACHE_EXPIRE_KM = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect KatMovieHD domain: {e}")

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for KatMovieHD: {mirror}")
            _CACHED_KM_DOMAIN = mirror
            _CACHE_EXPIRE_KM = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


def _parse_items_from_svelte(html: str, base_url: str) -> List[MovieItem]:
    """Parse items from SvelteKit SSR resolve script."""
    items = []
    # Match resolve({id:..., data:{success:true, data:{items:[...]}}})
    m = re.search(r'resolve\(\{id:\d+,data:\{success:true,data:\{items:(\[.*?\]),page:', html)
    if not m:
        m = re.search(r'items:(\[.*?\]),page:', html)

    if m:
        try:
            fixed = re.sub(r'([{,])([a-zA-Z0-9_]+):', r'\1"\2":', m.group(1))
            raw_list = json.loads(fixed)
            for it in raw_list:
                title = it.get("post_title") or it.get("title") or ""
                slug = it.get("slug") or it.get("id") or ""
                poster = it.get("thumbnail_image") or it.get("poster")
                if not title or not slug:
                    continue
                url = urljoin(base_url, f"/post/{slug}" if not slug.startswith("/") else slug)
                items.append(
                    MovieItem(
                        site="KatMovieHD",
                        title=title.replace("&amp;", "&").strip(),
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
        except Exception as err:
            LOGGER.debug(f"SvelteKit JSON parse failed: {err}")
    return items


async def scrape_katmoviehd() -> List[MovieItem]:
    """Scrape latest items from KatMovieHD."""
    base_url = await resolve_active_katmoviehd_domain()
    LOGGER.info(f"Fetching KatMovieHD releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch KatMovieHD HTML from {base_url}.")
        return []

    # 1. Try SvelteKit extraction
    items = _parse_items_from_svelte(html, base_url)
    if items:
        LOGGER.info(f"KatMovieHD scraper found {len(items)} items via SvelteKit data.")
        return items

    # 2. Traditional HTML fallback
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .item")
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
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()

            if title and url and len(title) > 5:
                items.append(
                    MovieItem(
                        site="KatMovieHD",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing KatMovieHD HTML: {e}")

    LOGGER.info(f"KatMovieHD scraper found {len(items)} items.")
    return items
