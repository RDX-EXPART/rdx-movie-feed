import asyncio
import json
import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from config import (
    ENABLE_BOLLYFLIX,
    ENABLE_CINEVOOD,
    ENABLE_CLOUDMOVIEZ,
    ENABLE_DOTMOVIES,
    ENABLE_EXTRAFLIX,
    ENABLE_FILMYCAB,
    ENABLE_FOURKHDHUB,
    ENABLE_HDHUB4U,
    ENABLE_KATDRAMA,
    ENABLE_KATMOVIEHD,
    ENABLE_MKVDRAMA,
    ENABLE_MLSBD,
    ENABLE_MOVIESMOD,
    ENABLE_TAMILMV,
    ENABLE_TOONWORLD,
    ENABLE_VEGAMOVIES,
    FOURKHDHUB_URL,
)
from scrapers.base import DEFAULT_HEADERS, MovieItem, fetch_html
from scrapers.bollyflix import extract_qualities as bf_qualities, resolve_active_bollyflix_domain
from scrapers.cinevood import extract_qualities as cv_qualities, resolve_active_cinevood_domain
from scrapers.cloudmoviez import search_cloudmoviez
from scrapers.dotmovies import extract_qualities as dm_qualities, resolve_active_dotmovies_domain
from scrapers.extraflix import extract_qualities as ef_qualities, resolve_active_extraflix_domain
from scrapers.filmycab import extract_qualities as fc_qualities, resolve_active_filmycab_domain
from scrapers.hdhub4u import extract_qualities as hd_qualities, resolve_active_hdhub4u_domain
from scrapers.katdrama import extract_qualities as kd_qualities, resolve_active_katdrama_domain
from scrapers.katmoviehd import (
    _parse_items_from_svelte as km_parse_svelte,
    extract_qualities as km_qualities,
    resolve_active_katmoviehd_domain,
)
from scrapers.mkvdrama import parse_mkvdrama_cards, resolve_active_mkvdrama_domain
from scrapers.mlsbd import extract_qualities as mlsbd_qualities
from scrapers.moviesmod import extract_qualities as mm_qualities, resolve_active_moviesmod_domain
from scrapers.tamilmv import search_tamilmv
from scrapers.toonworld import extract_qualities as tw_qualities, resolve_active_toonworld_domain
from scrapers.vegamovies import extract_qualities as vg_qualities, resolve_active_vega_domain

LOGGER = logging.getLogger("SearchEngine")


def _clean_post_title(title: str) -> str:
    title = re.sub(
        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}\s*",
        "",
        title,
        flags=re.I,
    ).strip()
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


async def search_filmycab(query: str, limit: int = 6) -> List[MovieItem]:
    """Search FilmyCab for movies and series."""
    base_url = await resolve_active_filmycab_domain()
    search_url = f"{base_url}/site-search.html"
    items = []
    seen = set()
    try:
        h = dict(DEFAULT_HEADERS)
        h["Content-Type"] = "application/x-www-form-urlencoded"
        h["Referer"] = base_url
        client_timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(search_url, data={"to-search": query}, headers=h) as resp:
                if resp.status == 200:
                    html = await resp.text(errors="ignore")
                    soup = BeautifulSoup(html, "html.parser")
                    thumbs = soup.select("div.thumb, div.rsz, figure, section.thumbnail-wrapper div.thumb")
                    for thumb in thumbs:
                        a = thumb.find("a", href=lambda val: val and val.endswith(".html"))
                        if not a or not a.get("href"):
                            continue
                        url = urljoin(base_url, a["href"])
                        if url in seen:
                            continue
                        seen.add(url)

                        img = thumb.find("img")
                        title = ""
                        poster = None
                        if img:
                            title = img.get("alt", "").strip()
                            poster = img.get("src") or img.get("data-src")
                            if poster:
                                poster = urljoin(base_url, poster)
                        if not title:
                            title = a.get_text(" ", strip=True)
                            title = re.sub(r"^(?:Download|Watch)\s*", "", title, flags=re.I).strip()

                        if not title:
                            slug = a["href"].rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ")
                            title = slug

                        quality = fc_qualities(title)
                        items.append(
                            MovieItem(
                                site="FilmyCab",
                                title=title,
                                url=url,
                                poster=poster,
                                quality=quality,
                            )
                        )
                        if len(items) >= limit:
                            break
    except Exception as e:
        LOGGER.debug(f"FilmyCab search error: {e}")
    return items


async def search_mkvdrama(query: str, limit: int = 6) -> List[MovieItem]:
    """Search MkvDrama for K-Drama, C-Drama & Asian movies/series."""
    base_url = await resolve_active_mkvdrama_domain()
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []
    return parse_mkvdrama_cards(html, base_url, limit=limit)


async def search_fourkhdhub(query: str, limit: int = 6) -> List[MovieItem]:
    """Search 4K-HDHub for 4K & UHD movies and series."""
    base_url = (FOURKHDHUB_URL or "https://4khdhub.one").rstrip("/")
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=re.compile(r"-(movie|series)-\d+/?$"))
        for a in links:
            href = a.get("href", "")
            url = urljoin(base_url, href)
            if url in seen:
                continue

            img = a.find("img")
            poster = None
            if img:
                poster = img.get("src") or img.get("data-src")
                if poster:
                    poster = urljoin(base_url, poster)

            raw_title = ""
            if img and img.get("alt"):
                raw_title = img["alt"].strip()
            elif a.get("aria-label"):
                raw_title = a["aria-label"].replace("details", "").strip()
            else:
                raw_title = a.get_text(strip=True)

            if not raw_title:
                continue

            badges = [b.get_text(strip=True) for b in a.select(".quality-badge, .movie-card-format")]
            qualities = []
            for b in badges:
                if any(q in b.upper() for q in ("4K", "2160P", "1080P", "720P", "HDR", "DV", "HEVC", "REMUX")):
                    if b.upper() not in qualities:
                        qualities.append(b.upper())
            quality_str = " | ".join(qualities) if qualities else "4K / HD"

            text = a.get_text(" ", strip=True)
            ep_match = re.search(r"(S\d+(?:-S\d+)?\s*(?:EP?\d+)?)", text, re.I)
            if ep_match and ep_match.group(1) not in raw_title:
                raw_title = f"{raw_title} ({ep_match.group(1)})"

            raw_title = _clean_post_title(raw_title)
            seen.add(url)
            items.append(
                MovieItem(
                    site="4K-HDHub",
                    title=raw_title,
                    url=url,
                    poster=poster,
                    quality=quality_str,
                )
            )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"4K-HDHub search error: {e}")
    return items


async def search_mlsbd(query: str, limit: int = 6) -> List[MovieItem]:
    """Search MLSBD for Bengali, Hindi & Hollywood releases."""
    base_url = "https://mlsbd.co"
    search_url = f"{base_url}/?s={quote_plus(query)}"
    html = await fetch_html(search_url, timeout=10)
    if not html:
        return []

    items = []
    seen = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith("https://mlsbd.co/") and not href.startswith("/"):
                continue
            url = urljoin(base_url, href)
            parts = [p for p in urlparse(url).path.split("/") if p]
            if len(parts) != 1 or parts[0] in (
                "author",
                "category",
                "tag",
                "how-to-download",
                "about-us",
                "contact-us",
                "review-news",
                "reviews",
                "stream",
                "dmca-information",
            ):
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 5 or any(ign in title.lower() for ign in ("how to download", "join us", "stream")):
                continue

            if url in seen:
                continue
            seen.add(url)

            quality = mlsbd_qualities(title)
            items.append(
                MovieItem(
                    site="MLSBD",
                    title=_clean_post_title(title),
                    url=url,
                    poster=None,
                    quality=quality,
                )
            )
            if len(items) >= limit:
                break
    except Exception as e:
        LOGGER.debug(f"MLSBD search error: {e}")
    return items


SITE_SEARCHERS = {
    "moviesmod": {
        "name": "MoviesMod",
        "emoji": "⚡",
        "func": search_moviesmod,
        "enabled": ENABLE_MOVIESMOD,
    },
    "vegamovies": {
        "name": "VegaMovies",
        "emoji": "⭐",
        "func": search_vegamovies,
        "enabled": ENABLE_VEGAMOVIES,
    },
    "hdhub4u": {
        "name": "HDHub4u",
        "emoji": "🎯",
        "func": search_hdhub4u,
        "enabled": ENABLE_HDHUB4U,
    },
    "fourkhdhub": {
        "name": "4K-HDHub",
        "emoji": "💎",
        "func": search_fourkhdhub,
        "enabled": ENABLE_FOURKHDHUB,
    },
    "bollyflix": {
        "name": "BollyFlix",
        "emoji": "🎬",
        "func": search_bollyflix,
        "enabled": ENABLE_BOLLYFLIX,
    },
    "cinevood": {
        "name": "CineVood",
        "emoji": "🍿",
        "func": search_cinevood,
        "enabled": ENABLE_CINEVOOD,
    },
    "katmoviehd": {
        "name": "KatMovieHD",
        "emoji": "🦁",
        "func": search_katmoviehd,
        "enabled": ENABLE_KATMOVIEHD,
    },
    "dotmovies": {
        "name": "DotMovies",
        "emoji": "🎪",
        "func": search_dotmovies,
        "enabled": ENABLE_DOTMOVIES,
    },
    "extraflix": {
        "name": "ExtraFlix",
        "emoji": "🍿",
        "func": search_extraflix,
        "enabled": ENABLE_EXTRAFLIX,
    },
    "filmycab": {
        "name": "FilmyCab",
        "emoji": "🚕",
        "func": search_filmycab,
        "enabled": ENABLE_FILMYCAB,
    },
    "tamilmv": {
        "name": "1TamilMV",
        "emoji": "🐯",
        "func": search_tamilmv,
        "enabled": ENABLE_TAMILMV,
    },
    "cloudmoviez": {
        "name": "CloudMoviez",
        "emoji": "🎬",
        "func": search_cloudmoviez,
        "enabled": ENABLE_CLOUDMOVIEZ,
    },
    "mkvdrama": {
        "name": "MkvDrama",
        "emoji": "🌸",
        "func": search_mkvdrama,
        "enabled": ENABLE_MKVDRAMA,
    },
    "katdrama": {
        "name": "KatDrama",
        "emoji": "🎭",
        "func": search_katdrama,
        "enabled": ENABLE_KATDRAMA,
    },
    "toonworld": {
        "name": "ToonWorld",
        "emoji": "🌀",
        "func": search_toonworld,
        "enabled": ENABLE_TOONWORLD,
    },
    "mlsbd": {
        "name": "MLSBD",
        "emoji": "🇧🇩",
        "func": search_mlsbd,
        "enabled": ENABLE_MLSBD,
    },
}


async def search_single_site(site_key: str, query: str, limit: int = 8) -> List[MovieItem]:
    """Execute search on a specific site."""
    query = query.strip()
    if not query:
        return []
    if site_key == "all":
        return await search_all_sites(query, max_total=limit * 2)
    entry = SITE_SEARCHERS.get(site_key)
    if not entry:
        LOGGER.warning(f"Unknown site key for search: {site_key}")
        return []
    try:
        return await entry["func"](query, limit=limit)
    except Exception as e:
        LOGGER.error(f"Error searching on {site_key}: {e}")
        return []


async def search_all_sites(query: str, max_total: int = 24) -> List[MovieItem]:
    """Search across all active movie & series websites concurrently."""
    query = query.strip()
    if not query:
        return []

    tasks = []
    for s_key, s_data in SITE_SEARCHERS.items():
        if s_data.get("enabled", True):
            tasks.append(s_data["func"](query))

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
