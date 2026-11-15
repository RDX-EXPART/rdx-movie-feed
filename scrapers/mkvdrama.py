import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import MKVDRAMA_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperMkvDrama")

_CACHED_MD_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_MD: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://mkvdrama.net",
    "https://mkvdrama.org",
]


def extract_qualities(text: str, extra_badges: Optional[List[str]] = None) -> str:
    matches = re.findall(r"\b(480[pP]|540[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL|Pack)\b", text, re.I)
    parts = list(dict.fromkeys([m.upper() for m in matches]))
    if not parts:
        parts.append("540P | 720P | 1080P")
    if extra_badges:
        for b in extra_badges:
            b_clean = b.strip()
            if b_clean and b_clean.upper() not in [p.upper() for p in parts]:
                parts.append(b_clean)
    return " | ".join(parts)


async def resolve_active_mkvdrama_domain() -> str:
    global _CACHED_MD_DOMAIN, _CACHE_EXPIRE_MD

    if MKVDRAMA_URL:
        return MKVDRAMA_URL

    now = time.time()
    if _CACHED_MD_DOMAIN and now < _CACHE_EXPIRE_MD:
        return _CACHED_MD_DOMAIN

    for mirror in FALLBACK_MIRRORS:
        test_html = await fetch_html(mirror, timeout=8, use_jina_fallback=False)
        if test_html and ("fe-row-card" in test_html or "mkvdrama" in test_html.lower()):
            LOGGER.info(f"Using working mirror for MkvDrama: {mirror}")
            _CACHED_MD_DOMAIN = mirror
            _CACHE_EXPIRE_MD = now + CACHE_TTL
            return mirror

    return FALLBACK_MIRRORS[0]


def parse_mkvdrama_cards(html: str, base_url: str, limit: int = 0) -> List[MovieItem]:
    items: List[MovieItem] = []
    seen_urls = set()

    try:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article.fe-row-card, article.bs, div.bs, article.post")
        for card in cards:
            a = card.select_one("a.fe-row-link, a.tip") or card.find("a", href=True)
            if not a or not a.get("href"):
                continue

            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            url = urljoin(base_url, href)
            if (
                url in seen_urls
                or url.rstrip("/") == base_url.rstrip("/")
                or any(
                    skip in url.lower()
                    for skip in (
                        "/category/",
                        "/tag/",
                        "/page/",
                        "/genre/",
                        "/country/",
                        "/ongoing-drama",
                        "/upcoming-drama",
                        "/request-drama",
                        "/drama-list",
                        "/faq",
                        "/dmca",
                        "/contact",
                    )
                )
            ):
                continue
            seen_urls.add(url)

            title_el = card.select_one(".fe-row-title, .tt h2, h2, h3, .entry-title, .title")
            title = title_el.get_text(" ", strip=True) if title_el else (a.get("title") or a.get_text(" ", strip=True))
            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()
            if not title or len(title) < 2:
                continue

            ep_el = card.select_one(".fe-ep-badge, .epx, .status")
            ep_text = ep_el.get_text(" ", strip=True) if ep_el else ""

            country_el = card.select_one(".fe-country-badge, .country, .typez")
            country_text = country_el.get_text(" ", strip=True) if country_el else ""

            if ep_text and ep_text.lower() not in title.lower():
                display_title = f"{title} [{ep_text}]"
            else:
                display_title = title

            img = card.find("img")
            poster = None
            if img:
                poster = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("data-original")
                )
                if poster and not poster.startswith("data:"):
                    poster = urljoin(base_url, poster)
                else:
                    poster = None

            badges = [b for b in (country_text, ep_text) if b]
            items.append(
                MovieItem(
                    site="MkvDrama",
                    title=display_title,
                    url=url,
                    poster=poster,
                    quality=extract_qualities(display_title, badges),
                )
            )
            if limit and len(items) >= limit:
                break
    except Exception as e:
        LOGGER.error(f"Error parsing MkvDrama HTML: {e}")

    return items


async def scrape_mkvdrama() -> List[MovieItem]:
    """Scrape latest K-Drama, C-Drama & Asian drama/movie releases from MkvDrama."""
    base_url = await resolve_active_mkvdrama_domain()
    LOGGER.info(f"Fetching MkvDrama releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch MkvDrama HTML from {base_url}.")
        return []

    items = parse_mkvdrama_cards(html, base_url)
    LOGGER.info(f"MkvDrama scraper found {len(items)} items.")
    return items
