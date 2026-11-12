import asyncio
import json
import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config import (
    ENABLE_BOLLYFLIX,
    ENABLE_CINEVOOD,
    ENABLE_DOTMOVIES,
    ENABLE_EXTRAFLIX,
    ENABLE_HDHUB4U,
    ENABLE_KATDRAMA,
    ENABLE_KATMOVIEHD,
    ENABLE_MOVIESMOD,
    ENABLE_TOONWORLD,
    ENABLE_VEGAMOVIES,
)
from scrapers.base import MovieItem, fetch_html
from scrapers.bollyflix import extract_qualities as bf_qualities, resolve_active_bollyflix_domain
from scrapers.cinevood import extract_qualities as cv_qualities, resolve_active_cinevood_domain
from scrapers.dotmovies import extract_qualities as dm_qualities, resolve_active_dotmovies_domain
from scrapers.extraflix import extract_qualities as ef_qualities, resolve_active_extraflix_domain
from scrapers.hdhub4u import extract_qualities as hd_qualities, resolve_active_hdhub4u_domain
from scrapers.katdrama import extract_qualities as kd_qualities, resolve_active_katdrama_domain
from scrapers.katmoviehd import (
    _parse_items_from_svelte as km_parse_svelte,
    extract_qualities as km_qualities,
    resolve_active_katmoviehd_domain,
)
from scrapers.moviesmod import extract_qualities as mm_qualities, resolve_active_moviesmod_domain
from scrapers.toonworld import extract_qualities as tw_qualities, resolve_active_toonworld_domain
from scrapers.vegamovies import extract_qualities as vg_qualities, resolve_active_vega_domain

LOGGER = logging.getLogger("SearchEngine")


def _clean_post_title(title: str) -> str:
    title = re.sub(r"^download\s+", "", title, flags=re.I).strip()
    return " ".join(title.split())


async def search_dotmovies(query: str, limit: int = 6) -> List[MovieItem]:
    """Search DotMovies for movies and series."""
    base_url = await resolve_active_dotmovies_domain()
    search_url = f"{base_url}/index.php?do=search&subaction=search&story={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item, .story-item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title, .story-title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="DotMovies",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=dm_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"DotMovies search error: {e}")
    return items


async def search_bollyflix(query: str, limit: int = 6) -> List[MovieItem]:
    """Search BollyFlix for Bollywood and dual audio movies."""
    base_url = await resolve_active_bollyflix_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="BollyFlix",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=bf_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"BollyFlix search error: {e}")
    return items


async def search_cinevood(query: str, limit: int = 6) -> List[MovieItem]:
    """Search CineVood / FilmyZilla for movies."""
    base_url = await resolve_active_cinevood_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="CineVood",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=cv_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"CineVood search error: {e}")
    return items


async def search_toonworld(query: str, limit: int = 6) -> List[MovieItem]:
    """Search ToonWorld4All for anime and cartoons."""
    base_url = await resolve_active_toonworld_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/", "/cdn-cgi/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="ToonWorld4All",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=tw_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"ToonWorld search error: {e}")
    return items


async def search_katdrama(query: str, limit: int = 6) -> List[MovieItem]:
    """Search KatDrama for Asian series."""
    base_url = await resolve_active_katdrama_domain()
    search_url = f"{base_url}/search?q={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        search_url = f"{base_url}/?s={quote_plus(query)}"
        html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    # 1. SvelteKit resolve
    m = re.search(r'resolve\(\{id:\d+,data:\{success:true,data:\{items:(\[.*?\]),page:', html)
    if not m:
        m = re.search(r'items:(\[.*?\]),page:', html)
    if m:
        try:
            fixed = re.sub(r'([{,])([a-zA-Z0-9_]+):', r'\1"\2":', m.group(1))
            raw_list = json.loads(fixed)
            for it in raw_list:
                title = it.get("post_title") or it.get("title") or ""
                slug = it.get("slug") or it.get("id") or ""
                poster = it.get("thumbnail_image") or it.get("poster")
                if not title or not slug:
                    continue
                url = urljoin(base_url, f"/post/{slug}" if not slug.startswith("/") else slug)
                items.append(
                    MovieItem(
                        site="KatDrama",
                        title=title.replace("&amp;", "&").strip(),
                        url=url,
                        poster=poster,
                        quality=kd_qualities(title),
                    )
                )
                if len(items) >= limit:
                    break
        except Exception:
            pass
    return items


async def search_katmoviehd(query: str, limit: int = 6) -> List[MovieItem]:
    """Search KatMovieHD for movies, series & dual audio."""
    base_url = await resolve_active_katmoviehd_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=12)
    if not html:
        return []

    items = []
    # 1. Try SvelteKit extraction
    svelte_items = km_parse_svelte(html, base_url)
    if svelte_items:
        for it in svelte_items:
            if "katdrama" in it.url.lower() or "new show updated" in it.title.lower():
                continue
            items.append(it)
            if len(items) >= limit:
                break
        if items:
            return items

    # 2. HTML fallback
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if (
                url in seen
                or url.endswith("#")
                or url.rstrip("/") == base_url.rstrip("/")
                or any(x in url for x in ("/category/", "/tag/", "/page/"))
            ):
                continue
            seen.add(url)
            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)
            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="KatMovieHD",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=km_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"KatMovieHD search error: {e}")
    return items


async def search_moviesmod(query: str, limit: int = 6) -> List[MovieItem]:
    """Search MoviesMod."""
    base_url = await resolve_active_moviesmod_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=12)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="MoviesMod",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=mm_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"MoviesMod search error: {e}")
    return items


async def search_extraflix(query: str, limit: int = 6) -> List[MovieItem]:
    """Search ExtraFlix."""
    base_url = await resolve_active_extraflix_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="ExtraFlix",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=ef_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"ExtraFlix search error: {e}")
    return items


async def search_hdhub4u(query: str, limit: int = 6) -> List[MovieItem]:
    """Search HDHub4u."""
    base_url = await resolve_active_hdhub4u_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .result-item, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="HDHub4u",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=hd_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"HDHub4u search error: {e}")
    return items


async def search_vegamovies(query: str, limit: int = 6) -> List[MovieItem]:
    """Search VegaMovies."""
    base_url = await resolve_active_vega_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=12)
    if not html:
        search_url = f"{base_url}/search/{quote_plus(query)}"
        html = await fetch_html(search_url, timeout=12)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select("article, div.post, .post-item, div.latest-post, .item")
        for p in posts:
            a = p.find("a")
            if not a or not a.get("href"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or url.endswith("#") or url.rstrip("/") == base_url.rstrip("/") or any(x in url for x in ("/category/", "/tag/", "/page/")):
                continue
            seen.add(url)

            img = p.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if poster:
                    poster = urljoin(base_url, poster)

            heading = p.select_one("h1, h2, h3, .entry-title, .title")
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            title = _clean_post_title(title)
            if title and len(title) > 4:
                items.append(
                    MovieItem(
                        site="VegaMovies",
                        title=title,
                        url=url,
                        poster=poster,
                        quality=vg_qualities(title),
                    )
                )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"VegaMovies search error: {e}")
    return items


async def search_all_sites(query: str, max_total: int = 24) -> List[MovieItem]:
    """Search across all active movie & series websites concurrently."""
    query = query.strip()
    if not query:
        return []

    tasks = []
    if ENABLE_DOTMOVIES:
        tasks.append(search_dotmovies(query))
    if ENABLE_BOLLYFLIX:
        tasks.append(search_bollyflix(query))
    if ENABLE_CINEVOOD:
        tasks.append(search_cinevood(query))
    if ENABLE_TOONWORLD:
        tasks.append(search_toonworld(query))
    if ENABLE_KATMOVIEHD:
        tasks.append(search_katmoviehd(query))
    if ENABLE_KATDRAMA:
        tasks.append(search_katdrama(query))
    if ENABLE_MOVIESMOD:
        tasks.append(search_moviesmod(query))
    if ENABLE_EXTRAFLIX:
        tasks.append(search_extraflix(query))
    if ENABLE_HDHUB4U:
        tasks.append(search_hdhub4u(query))
    if ENABLE_VEGAMOVIES:
        tasks.append(search_vegamovies(query))

    if not tasks:
        LOGGER.warning("No search sources enabled!")
        return []

    LOGGER.info(f"Executing search for query '{query}' across {len(tasks)} platforms...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    combined: List[MovieItem] = []
    seen_urls = set()
    for res in results:
        if isinstance(res, list):
            for item in res:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    combined.append(item)

    LOGGER.info(f"Search for '{query}' returned {len(combined)} total results.")
    return combined[:max_total]
