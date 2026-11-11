import logging
import re
import xml.etree.ElementTree as ET
from typing import List

from bs4 import BeautifulSoup

from config import MLSBD_FEED
from scrapers.base import MovieItem, fetch_html

LOGGER = logging.getLogger("ScraperMLSBD")


def extract_qualities(text: str) -> str:
    matches = re.findall(r"\b(480[pP]|720[pP]|1080[pP]|2160[pP]|4[kK]|HEVC|HDR|WEB-DL)\b", text, re.I)
    if matches:
        return " | ".join(dict.fromkeys([m.upper() for m in matches]))
    return "HD"


async def fetch_mlsbd_poster(url: str) -> str:
    """Fetch poster for an MLSBD post using Jina AI reader fallback."""
    if not url:
        return None
    try:
        jina_url = f"https://r.jina.ai/{url}"
        html = await fetch_html(jina_url, use_jina_fallback=False, timeout=8)
        if html:
            imgs = re.findall(
                r"!\[.*?\]\((https?://(?:cdn\.imgnest\.io|mlsbd\.co/wp-content/uploads)/[^\)]+\.(?:webp|jpg|jpeg|png))\)",
                html,
                re.I,
            )
            valid = [img for img in imgs if "logo" not in img.lower()]
            if valid:
                return valid[0]
    except Exception as e:
        LOGGER.debug(f"Failed to fetch MLSBD poster for {url}: {e}")
    return None


async def scrape_mlsbd() -> List[MovieItem]:
    """Scrape latest items from MLSBD WordPress RSS feed."""
    LOGGER.info(f"Fetching MLSBD feed from {MLSBD_FEED}...")
    xml_data = await fetch_html(MLSBD_FEED, use_jina_fallback=False)
    if not xml_data:
        LOGGER.warning("Failed to fetch MLSBD feed XML.")
        return []

    items = []
    try:
        # Try XML parser first
        root = ET.fromstring(xml_data.strip())
        xml_items = root.findall("./channel/item")
        for it in xml_items:
            title_elem = it.find("title")
            link_elem = it.find("link")
            guid_elem = it.find("guid")
            pub_date = it.find("pubDate")
            desc_elem = it.find("description")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            if not url and guid_elem is not None and guid_elem.text:
                url = guid_elem.text.strip()

            date_str = pub_date.text.strip() if pub_date is not None and pub_date.text else ""

            poster = None
            if desc_elem is not None and desc_elem.text:
                d_soup = BeautifulSoup(desc_elem.text, "html.parser")
                img = d_soup.find("img")
                if img:
                    poster = img.get("src")

            if title and url:
                quality = extract_qualities(title)
                items.append(
                    MovieItem(
                        site="MLSBD",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=quality,
                        date=date_str,
                    )
                )
    except Exception as e:
        LOGGER.warning(f"ET XML parsing failed ({e}), falling back to BeautifulSoup...")
        try:
            soup = BeautifulSoup(xml_data, "html.parser")
            for it in soup.find_all("item"):
                t = it.find("title")
                l = it.find("guid") or it.find("link")
                title = t.get_text(strip=True) if t else ""
                url = l.get_text(strip=True) if l else ""
                if title and url:
                    items.append(
                        MovieItem(
                            site="MLSBD",
                            title=title,
                            url=url,
                            poster=None,
                            quality=extract_qualities(title),
                        )
                    )
        except Exception as be:
            LOGGER.error(f"BS4 fallback also failed for MLSBD: {be}")

    LOGGER.info(f"MLSBD scraper found {len(items)} items.")
    return items
