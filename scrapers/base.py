import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import aiohttp

LOGGER = logging.getLogger("ScraperBase")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


@dataclass
class MovieItem:
    site: str
    title: str
    url: str
    poster: Optional[str] = None
    quality: Optional[str] = None
    date: Optional[str] = None
    extra_info: Optional[str] = None

    def clean_title(self) -> str:
        t = self.title or ""
        t = " ".join(t.split())
        return t.strip()


async def fetch_html(
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 15,
    allow_redirects: bool = True,
    use_jina_fallback: bool = True,
) -> Optional[str]:
    """Fetch URL contents with async aiohttp and optional Jina AI reader fallback on Cloudflare blocks."""
    if not url:
        return None

    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)

    client_timeout = aiohttp.ClientTimeout(total=timeout)
    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(url, headers=h, allow_redirects=allow_redirects) as resp:
                if resp.status == 200:
                    return await resp.text(errors="ignore")
                elif resp.status in (403, 502, 503) and use_jina_fallback:
                    LOGGER.info(f"Got {resp.status} for {url}, attempting Jina AI reader fallback...")
                    jina_url = f"https://r.jina.ai/{url}"
                    async with session.get(jina_url, headers={"User-Agent": DEFAULT_HEADERS["User-Agent"]}) as jresp:
                        if jresp.status == 200:
                            return await jresp.text(errors="ignore")
                LOGGER.warning(f"Failed to fetch {url} (HTTP {resp.status})")
    except Exception as e:
        LOGGER.error(f"Error fetching {url}: {e}")
        if use_jina_fallback:
            try:
                jina_url = f"https://r.jina.ai/{url}"
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.get(jina_url, headers={"User-Agent": DEFAULT_HEADERS["User-Agent"]}) as jresp:
                        if jresp.status == 200:
                            return await jresp.text(errors="ignore")
            except Exception as je:
                LOGGER.debug(f"Jina fallback also failed for {url}: {je}")
    return None
