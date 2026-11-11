import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import VEGA_HUB_URL, VEGAMOVIES_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperVega")

_CACHED_VEGA_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_VEGA: float = 0
CACHE_TTL = 3600  # 1 hour cache

FALLBACK_MIRRORS = [
    "https://vegamovies.lease",
    "https://1vegamovies.tw",
    "https://vegamovis.skin",
    "https://vegamovies.domains",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|HDRip|WEB-DL|Blu-Ray)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_vega_domain() -> str:
    """Auto-detect the latest VegaMovies domain via 1vegamovies.buzz or user config."""
    global _CACHED_VEGA_DOMAIN, _CACHE_EXPIRE_VEGA

    # 1. Manual override from config
    if VEGAMOVIES_URL:
        return VEGAMOVIES_URL

    # 2. In-memory cache
    now = time.time()
    if _CACHED_VEGA_DOMAIN and now < _CACHE_EXPIRE_VEGA:
        return _CACHED_VEGA_DOMAIN

    LOGGER.info(f"Auto-detecting active VegaMovies domain from hub {VEGA_HUB_URL}...")
    try:
        html = await fetch_html(VEGA_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if "vegamovies" in href.lower() and href.startswith("http"):
                    detected = href.rstrip("/")
                    LOGGER.info(f"Auto-detected VegaMovies domain from hub: {detected}")
                    _CACHED_VEGA_DOMAIN = detected
                    _CACHE_EXPIRE_VEGA = now + CACHE_TTL
                    return detected

            # Regex search in raw HTML text
            m = re.search(r"https?://[a-zA-Z0-9\.\-]*vegamovies\.[a-zA-Z0-9\.\-]+", html, re.I)
            if m:
                detected = m.group(0).rstrip("/")
                LOGGER.info(f"Auto-detected VegaMovies domain via regex: {detected}")
                _CACHED_VEGA_DOMAIN = detected
                _CACHE_EXPIRE_VEGA = now + CACHE_TTL
                return detected
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect from Vega hub: {e}")

    # 3. Test fallback mirrors
    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=6, use_jina_fallback=False)
        if test_html:
            LOGGER.info(f"Using working fallback mirror for VegaMovies: {mirror}")
            _CACHED_VEGA_DOMAIN = mirror
            _CACHE_EXPIRE_VEGA = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


async def _scrape_single_mirror(base_url: str) -> List[MovieItem]:
    """Scrape a specific VegaMovies mirror."""
    html = await fetch_html(base_url)
    items = []

    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            selectors = "div.movies-grid a, .content-section a, article, div.post, .post-item, div.blog-post"
            containers = soup.select(selectors)

            candidate_links = []
            if containers:
                for c in containers:
                    if c.name == "a":
                        candidate_links.append(c)
                    else:
                        a = c.find("a")
                        if a:
                            candidate_links.append(a)
            else:
                candidate_links = soup.find_all(
                    "a",
                    href=re.compile(r"/(?:download-[^/]+|[^/]+-(?:480p|720p|1080p|web-dl|bluray)[^/]*)/?$"),
                )

            for a in candidate_links:
                href = a.get("href", "")
                if not href or href == "#" or "/category/" in href or "/page/" in href:
                    continue
                url = urljoin(base_url, href)

                img = a.find("img")
                poster = None
                title = ""

                if img:
                    poster = (
                        img.get("data-src")
                        or img.get("src")
                        or img.get("data-lazy-src")
                        or img.get("data-cfsrc")
                    )
                    if poster and poster.startswith("data:"):
                        poster = None
                    if poster:
                        poster = urljoin(base_url, poster)

                    alt = img.get("alt", "").strip()
                    if alt and len(alt) > 5 and not alt.isdigit() and "download now" not in alt.lower():
                        title = alt

                if not title:
                    if a.get("title") and len(a["title"].strip()) > 5:
                        title = a["title"].strip()
                    else:
                        parent = a.find_parent(["article", "div", "section"])
                        heading = parent.select_one("h1, h2, h3, .entry-title, .title") if parent else None
                        if heading:
                            title = heading.get_text(strip=True)
                        else:
                            txt = a.get_text(" ", strip=True)
                            if len(txt) > 8 and "download" in txt.lower():
                                title = txt

                # Clean title
                title = re.sub(r"^(?:[A-Za-z]+ \d{1,2}, \d{4}\s*)+", "", title).strip()
                title = re.sub(r"^(?:WEB-DL|Blu-Ray|HDRip|⭐\s*[\d\.]+/10)\s*", "", title, flags=re.I).strip()

                if title and url and len(title) > 5 and not title.lower().startswith("download now"):
                    items.append(
                        MovieItem(
                            site="VegaMovies",
                            title=title,
                            url=url,
                            poster=poster,
                            quality=extract_qualities(title),
                        )
                    )
        except Exception as e:
            LOGGER.debug(f"Error parsing Vega mirror {base_url}: {e}")

    # Fallback to RSS feed if homepage was empty
    if not items:
        feed_url = f"{base_url}/feed/"
        xml_data = await fetch_html(feed_url, use_jina_fallback=False)
        if xml_data:
            try:
                soup = BeautifulSoup(xml_data, "html.parser")
                for it in soup.find_all("item"):
                    t = it.find("title")
                    g = it.find("guid") or it.find("link")
                    title = t.get_text(strip=True) if t else ""
                    url = g.get_text(strip=True) if g else ""
                    if title and url:
                        items.append(
                            MovieItem(
                                site="VegaMovies",
                                title=title,
                                url=url,
                                poster=None,
                                quality=extract_qualities(title),
                            )
                        )
            except Exception as fe:
                LOGGER.debug(f"Error parsing Vega feed {feed_url}: {fe}")

    return items


async def scrape_vegamovies() -> List[MovieItem]:
    """Scrape latest items from VegaMovies with auto-detection and mirror rotation."""
    active_domain = await resolve_active_vega_domain()
    mirrors_to_try = list(dict.fromkeys([active_domain] + FALLBACK_MIRRORS))

    items = []
    working_mirror = None

    for mirror in mirrors_to_try:
        try:
            items = await _scrape_single_mirror(mirror)
            if items:
                working_mirror = mirror
                LOGGER.info(f"Successfully scraped {len(items)} items from VegaMovies: {working_mirror}")
                break
        except Exception as e:
            LOGGER.warning(f"VegaMovies mirror {mirror} failed: {e}. Trying next mirror...")

    # Deduplicate by url
    seen_urls = set()
    unique_items = []
    for it in items:
        if it.url not in seen_urls:
            seen_urls.add(it.url)
            unique_items.append(it)

    return unique_items
