import logging
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import SKYMOVIES_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperSkyMovies")


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|HDRip|DS4K|WEB-DL)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def scrape_skymovieshd() -> List[MovieItem]:
    """Scrape latest items from SkyMoviesHD."""
    LOGGER.info(f"Fetching SkyMoviesHD releases from {SKYMOVIES_URL}...")
    html = await fetch_html(SKYMOVIES_URL)
    if not html:
        LOGGER.warning("Failed to fetch SkyMoviesHD HTML.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Target movie release links
        links = soup.find_all("a", href=re.compile(r"/movie/.*\.html"))
        for a in links:
            href = a.get("href", "")
            url = urljoin(SKYMOVIES_URL, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img = a.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src")

            title = a.get_text(strip=True)
            # If title is in child text or heading
            if not title and img and img.get("alt"):
                title = img["alt"].strip()

            if title and url and len(title) > 5:
                items.append(
                    MovieItem(
                        site="SkyMoviesHD",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing SkyMoviesHD: {e}")

    LOGGER.info(f"SkyMoviesHD scraper found {len(items)} items.")
    return items
