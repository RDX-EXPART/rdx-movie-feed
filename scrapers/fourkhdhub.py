import logging
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import FOURKHDHUB_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("Scraper4KHDHub")


async def scrape_fourkhdhub() -> List[MovieItem]:
    """Scrape latest 4K and HD releases from 4K-HDHub."""
    LOGGER.info(f"Fetching 4K-HDHub releases from {FOURKHDHUB_URL}...")
    html = await fetch_html(FOURKHDHUB_URL)
    if not html:
        LOGGER.warning("Failed to fetch 4K-HDHub HTML.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Target movie and series cards
        links = soup.find_all("a", href=re.compile(r"-(movie|series)-\d+/?$"))
        for a in links:
            href = a.get("href", "")
            url = urljoin(FOURKHDHUB_URL, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img = a.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src")

            # Extract title: img alt usually contains the clean name
            raw_title = ""
            if img and img.get("alt"):
                raw_title = img["alt"].strip()
            elif a.get("aria-label"):
                raw_title = a["aria-label"].replace("details", "").strip()
            else:
                raw_title = a.get_text(strip=True)

            # Quality badges
            badges = [b.get_text(strip=True) for b in a.select(".quality-badge, .movie-card-format")]
            qualities = []
            for b in badges:
                if any(q in b.upper() for q in ("4K", "2160P", "1080P", "720P", "HDR", "DV", "HEVC", "REMUX")):
                    if b.upper() not in qualities:
                        qualities.append(b.upper())
            quality_str = " | ".join(qualities) if qualities else "4K / HD"

            # Check for season/episode info in text
            text = a.get_text(" ", strip=True)
            ep_match = re.search(r"(S\d+(?:-S\d+)?\s*(?:EP?\d+)?)", text, re.I)
            if ep_match and ep_match.group(1) not in raw_title:
                raw_title = f"{raw_title} ({ep_match.group(1)})"

            if raw_title and url:
                items.append(
                    MovieItem(
                        site="4K-HDHub",
                        title=raw_title,
                        url=url,
                        poster=poster,
                        quality=quality_str,
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing 4K-HDHub: {e}")

    LOGGER.info(f"4K-HDHub scraper found {len(items)} items.")
    return items
