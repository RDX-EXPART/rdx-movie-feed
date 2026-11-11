import logging
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import MOVIESMOD_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperMoviesMod")


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def scrape_moviesmod() -> List[MovieItem]:
    """Scrape latest items from MoviesMod."""
    LOGGER.info(f"Fetching MoviesMod releases from {MOVIESMOD_URL}...")
    html = await fetch_html(MOVIESMOD_URL)
    if not html:
        LOGGER.warning("Failed to fetch MoviesMod HTML.")
        return []

    items = []
    seen_urls = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(MOVIESMOD_URL, a["href"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(MOVIESMOD_URL, poster)

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

            # Strip redundant words like "Download " from start
            title = re.sub(r"^download\s+", "", title, flags=re.I).strip()

            if title and url and len(title) > 5:
                items.append(
                    MovieItem(
                        site="MoviesMod",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=extract_qualities(title),
                    )
                )
    except Exception as e:
        LOGGER.error(f"Error parsing MoviesMod: {e}")

    LOGGER.info(f"MoviesMod scraper found {len(items)} items.")
    return items
