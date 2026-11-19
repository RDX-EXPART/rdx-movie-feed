import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import aiohttp

try:
    from curl_cffi.requests import AsyncSession as CffiAsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

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


def _is_valid_html(text: str) -> bool:
    if not text or len(text) <= 200:
        return False
    return not any(
        k in text
        for k in (
            "<title>Just a moment...</title>",
            "Title: Just a moment...",
            "<title>Attention Required!",
            'id="challenge-error-text"',
            "cf-browser-verification",
            "Performing security verification",
        )
    )


async def _fetch_via_gtranslate(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetch Cloudflare-blocked pages via Google Translate proxy and restore original links."""
    import re
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return None
        gt_host = host.replace("-", "--").replace(".", "-") + ".translate.goog"
        path = parsed.path or "/"
        q_part = f"?{parsed.query}&" if parsed.query else "?"
        gt_url = f"https://{gt_host}{path}{q_part}_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en"
        async with session.get(gt_url, headers={"User-Agent": DEFAULT_HEADERS["User-Agent"]}) as resp:
            if resp.status == 200:
                text = await resp.text(errors="ignore")
                if _is_valid_html(text):
                    esc_gt = re.escape(gt_host)
                    text = re.sub(
                        rf"https?://{esc_gt}/([^\s\"'\?#]*)(?:\?[^\"'\s>]*)?",
                        rf"https://{host}/\1",
                        text,
                    )
                    return text
    except Exception as e:
        LOGGER.debug(f"Google Translate proxy fallback failed for {url}: {e}")
    return None


async def _fetch_via_cffi(url: str, headers: Optional[dict] = None, timeout: int = 15) -> Optional[str]:
    """Fetch URL using curl_cffi with browser TLS impersonation to bypass Cloudflare."""
    if not HAS_CURL_CFFI:
        return None
    try:
        async with CffiAsyncSession(impersonate="chrome120") as s:
            resp = await s.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and _is_valid_html(resp.text):
                return resp.text
    except Exception as e:
        LOGGER.debug(f"curl_cffi fetch fallback failed for {url}: {e}")
    return None


async def _fetch_via_proxy_api(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetch URL via custom PROXY_API_URL / bypass resolver if configured."""
    try:
        from config import PROXY_API_URL
    except Exception:
        PROXY_API_URL = ""
    if not PROXY_API_URL:
        return None
    try:
        base = PROXY_API_URL.rstrip("/")
        req_url = f"{base}/bypass?url={url}" if "/bypass" not in base else (f"{base}{url}" if "?url=" in base else f"{base}?url={url}")
        async with session.get(req_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                ct = resp.headers.get("content-type", "")
                if "application/json" in ct:
                    data = await resp.json()
                    html = data.get("html") or data.get("content") or ""
                    if html and _is_valid_html(html):
                        return html
                else:
                    text = await resp.text(errors="ignore")
                    if _is_valid_html(text):
                        return text
    except Exception as e:
        LOGGER.debug(f"Proxy API fallback failed for {url}: {e}")
    return None


async def fetch_html(
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 15,
    allow_redirects: bool = True,
    use_jina_fallback: bool = True,
) -> Optional[str]:
    """Fetch URL contents with async aiohttp, curl_cffi, Jina AI & Google Translate fallbacks."""
    if not url:
        return None

    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)

    client_timeout = aiohttp.ClientTimeout(total=timeout)
    jina_headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "x-return-format": "html",
    }
    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(url, headers=h, allow_redirects=allow_redirects) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="ignore")
                    if _is_valid_html(text):
                        return text
                if resp.status in (200, 403, 502, 503) and use_jina_fallback:
                    LOGGER.info(f"Cloudflare challenge/status {resp.status} for {url}, attempting fallbacks...")
                    # 1. curl_cffi TLS fingerprint impersonation
                    cffi_text = await _fetch_via_cffi(url, headers=h, timeout=timeout)
                    if cffi_text:
                        return cffi_text
                    # 2. PROXY_API_URL if configured
                    proxy_text = await _fetch_via_proxy_api(session, url)
                    if proxy_text:
                        return proxy_text
                    # 3. Jina AI reader fallback
                    try:
                        jina_url = f"https://r.jina.ai/{url}"
                        async with session.get(jina_url, headers=jina_headers) as jresp:
                            if jresp.status == 200:
                                jtext = await jresp.text(errors="ignore")
                                if _is_valid_html(jtext):
                                    return jtext
                    except Exception:
                        pass
                    # 4. Google Translate proxy fallback
                    gt_text = await _fetch_via_gtranslate(session, url)
                    if gt_text:
                        return gt_text
                LOGGER.warning(f"Failed to fetch {url} (HTTP {resp.status})")
    except Exception as e:
        LOGGER.error(f"Error fetching {url}: {e}")
        if use_jina_fallback:
            try:
                # 1. curl_cffi TLS impersonation
                cffi_text = await _fetch_via_cffi(url, headers=h, timeout=timeout)
                if cffi_text:
                    return cffi_text
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    # 2. PROXY_API_URL
                    proxy_text = await _fetch_via_proxy_api(session, url)
                    if proxy_text:
                        return proxy_text
                    # 3. Jina
                    try:
                        jina_url = f"https://r.jina.ai/{url}"
                        async with session.get(jina_url, headers=jina_headers) as jresp:
                            if jresp.status == 200:
                                jtext = await jresp.text(errors="ignore")
                                if _is_valid_html(jtext):
                                    return jtext
                    except Exception:
                        pass
                    # 4. Google Translate
                    gt_text = await _fetch_via_gtranslate(session, url)
                    if gt_text:
                        return gt_text
            except Exception as je:
                LOGGER.debug(f"Fallback also failed for {url}: {je}")
    return None

