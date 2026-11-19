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
    "https://filmycab.store",
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
        try:
            test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
            if test_html:
                LOGGER.info(f"Using working mirror for FilmyCab: {mirror}")
                _CACHED_FC_DOMAIN = mirror
                _CACHE_EXPIRE_FC = now + CACHE_TTL
                return mirror
        except Exception:
            continue

    return FALLBACK_MIRRORS[0]


def _parse_filmycab_html(html: str, base_url: str) -> List[MovieItem]:
    """Parse releases from either modern filmycab.store or classic filmycab layout."""
    items = []
    seen_urls = set()
    soup = BeautifulSoup(html, "html.parser")

    # 1. FilmyCab Store modern layout (.fch-card, .fch-slide)
    cards = soup.select("a.fch-card, article.fch-slide")
    if cards:
        for c in cards:
            a = c if c.name == "a" else c.find("a", href=True)
            if not a or not a.get("href"):
                continue
            href = a["href"].strip()
            url = urljoin(base_url, href)
            if url in seen_urls or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen_urls.add(url)

            img = c.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src")
                if poster:
                    poster = urljoin(base_url, poster)

            h = c.find(["h2", "h3", "h4"])
            raw_title = h.get_text(strip=True) if h else a.get_text(" ", strip=True)
            raw_title = re.sub(r"^[#\s]+", "", raw_title).strip()
            raw_title = re.sub(r"^(?:Download|Watch)\s*", "", raw_title, flags=re.I).strip()
            if not raw_title:
                raw_title = url.rstrip("/").split("/")[-1].replace("-", " ")

            if raw_title and len(raw_title) > 3:
                items.append(
                    MovieItem(
                        site="FilmyCab",
                        title=raw_title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(raw_title),
                    )
                )
        if items:
            return items

    # 2. FilmyCab classic layout (thumbs, figure)
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
    return items


async def scrape_filmycab() -> List[MovieItem]:
    """Scrape latest releases from FilmyCab with mirror fallback."""
    global _CACHED_FC_DOMAIN, _CACHE_EXPIRE_FC
    base_url = await resolve_active_filmycab_domain()
    LOGGER.info(f"Fetching FilmyCab releases from {base_url}...")

    html = await fetch_html(base_url)
    items = _parse_filmycab_html(html, base_url) if html else []

    if items:
        LOGGER.info(f"Successfully scraped {len(items)} items from FilmyCab ({base_url}).")
        return items

    # Fallback retry across other mirrors
    LOGGER.warning(f"FilmyCab primary mirror {base_url} returned 0 items. Retrying fallback mirrors...")
    for mirror in FALLBACK_MIRRORS:
        if mirror.rstrip("/") == base_url.rstrip("/"):
            continue
        try:
            m_html = await fetch_html(mirror, timeout=8)
            if not m_html:
                continue
            m_items = _parse_filmycab_html(m_html, mirror)
            if m_items:
                LOGGER.info(f"FilmyCab scraper succeeded via mirror {mirror} with {len(m_items)} items.")
                _CACHED_FC_DOMAIN = mirror
                _CACHE_EXPIRE_FC = time.time() + CACHE_TTL
                return m_items
        except Exception as me:
            LOGGER.debug(f"FilmyCab mirror {mirror} failed: {me}")

    LOGGER.info(f"FilmyCab scraper found 0 items across all mirrors.")
    return []
