import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import CINEVOOD_HUB_URL, CINEVOOD_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperCineVood")

_CACHED_CV_DOMAIN: Optional[str] = None
_CACHE_EXPIRE_CV: float = 0
CACHE_TTL = 3600

FALLBACK_MIRRORS = [
    "https://one.1cinevood.baby",
    "https://cinevood.coupons/",
    "https://cinevood.garden",
    "https://cinevood.net",
]


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL|BluRay|PreDVDRip|HDRip)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def resolve_active_cinevood_domain() -> str:
    global _CACHED_CV_DOMAIN, _CACHE_EXPIRE_CV

    if CINEVOOD_URL:
        return CINEVOOD_URL

    now = time.time()
    if _CACHED_CV_DOMAIN and now < _CACHE_EXPIRE_CV:
        return _CACHED_CV_DOMAIN

    LOGGER.info(f"Auto-detecting CineVood domain from hub {CINEVOOD_HUB_URL}...")
    candidates = []
    try:
        html = await fetch_html(CINEVOOD_HUB_URL, timeout=8, use_jina_fallback=False)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            from urllib.parse import urlparse
            hub_host = urlparse(CINEVOOD_HUB_URL).netloc.lower()
            for a in soup.find_all("a"):
                href = a.get("href", "").strip()
                if not href.startswith("http"):
                    continue
                p = urlparse(href)
                cand_host = p.netloc.lower()
                if not cand_host or cand_host == hub_host:
                    continue
                if any(ign in cand_host for ign in ("telegram", "t.me", "whatsapp", "twitter", "facebook")):
                    continue
                if "cinevood" in cand_host:
                    cand_url = f"{p.scheme}://{cand_host}".rstrip("/")
                    if cand_url not in candidates:
                        candidates.append(cand_url)
    except Exception as e:
        LOGGER.warning(f"Failed to auto-detect CineVood domain from hub: {e}")

    for cand in candidates + FALLBACK_MIRRORS:
        try:
            test_html = await fetch_html(cand, timeout=7, use_jina_fallback=False)
            if test_html:
                soup = BeautifulSoup(test_html, "html.parser")
                posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
                if len(posts) > 0:
                    LOGGER.info(f"Verified working CineVood domain: {cand} ({len(posts)} posts)")
                    _CACHED_CV_DOMAIN = cand
                    _CACHE_EXPIRE_CV = now + CACHE_TTL
                    return cand
        except Exception:
            continue

    return FALLBACK_MIRRORS[0]


async def scrape_cinevood() -> List[MovieItem]:
    """Scrape latest items from CineVood."""
    base_url = await resolve_active_cinevood_domain()
    LOGGER.info(f"Fetching CineVood releases from {base_url}...")

    html = await fetch_html(base_url)
    if not html:
        LOGGER.warning(f"Failed to fetch CineVood HTML from {base_url}.")
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
                        site="CineVood",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing CineVood: {e}")

    LOGGER.info(f"CineVood scraper found {len(items)} items.")
    return items
