import logging
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import VEGAMOVIES_URL
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperVega")


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|HDRip|WEB-DL)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def scrape_vegamovies() -> List[MovieItem]:
    """Scrape latest items from VegaMovies homepage or feed."""
    LOGGER.info(f"Fetching VegaMovies releases from {VEGAMOVIES_URL}...")
    html = await fetch_html(VEGAMOVIES_URL)
    items = []

    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Posts are usually in article, div.post, or .post-item
            posts = soup.select("article, div.post, .post-item, div.blog-post")
            for p in posts:
                a = p.find("a")
                if not a or not a.get("href"):
                    continue
                url = urljoin(VEGAMOVIES_URL, a["href"])
                img = p.find("img")
                poster = None
                if img:
                    poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                    if poster:
                        poster = urljoin(VEGAMOVIES_URL, poster)

                # Title: a['title'] is the cleanest on VegaMovies
                title = ""
                if a.get("title"):
                    title = a["title"].strip()
                else:
                    heading = p.select_one("h1, h2, h3, .entry-title, .title")
                    if heading:
                        raw = heading.get_text(strip=True)
                        # Remove prepended dates like "October 5, 2026"
                        raw = re.sub(r"^(?:[A-Za-z]+ \d{1,2}, \d{4}\s*)+", "", raw).strip()
                        title = raw
                    elif img and img.get("alt") and not img["alt"].isdigit():
                        title = img["alt"].strip()
                    elif a.get_text(strip=True):
                        title = a.get_text(strip=True)

                if title and url and len(title) > 5:
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
            LOGGER.error(f"Error parsing VegaMovies homepage: {e}")

    # Fallback to /feed/ if homepage returned nothing
    if not items:
        feed_url = f"{VEGAMOVIES_URL}/feed/"
        LOGGER.info(f"VegaMovies homepage empty, trying RSS feed: {feed_url}...")
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
                LOGGER.error(f"Error parsing VegaMovies feed: {fe}")

    # Deduplicate by url
    seen_urls = set()
    unique_items = []
    for it in items:
        if it.url not in seen_urls:
            seen_urls.add(it.url)
            unique_items.append(it)

    LOGGER.info(f"VegaMovies scraper found {len(unique_items)} items.")
    return unique_items
