import asyncio
import logging
from typing import List

from config import (
    ENABLE_BOLLYFLIX,
    ENABLE_CINEVOOD,
    ENABLE_DOTMOVIES,
    ENABLE_EXTRAFLIX,
    ENABLE_FOURKHDHUB,
    ENABLE_HDHUB4U,
    ENABLE_KATDRAMA,
    ENABLE_KATMOVIEHD,
    ENABLE_MLSBD,
    ENABLE_MOVIESMOD,
    ENABLE_SKYMOVIES,
    ENABLE_TOONWORLD,
    ENABLE_VEGAMOVIES,
)
from scrapers.base import MovieItem
from scrapers.bollyflix import scrape_bollyflix
from scrapers.cinevood import scrape_cinevood
from scrapers.dotmovies import scrape_dotmovies
from scrapers.extraflix import scrape_extraflix
from scrapers.fourkhdhub import scrape_fourkhdhub
from scrapers.hdhub4u import scrape_hdhub4u
from scrapers.katdrama import scrape_katdrama
from scrapers.katmoviehd import scrape_katmoviehd
from scrapers.mlsbd import scrape_mlsbd
from scrapers.moviesmod import scrape_moviesmod
from scrapers.skymovieshd import scrape_skymovieshd
from scrapers.toonworld import scrape_toonworld
from scrapers.vegamovies import scrape_vegamovies

LOGGER = logging.getLogger("ScraperManager")


async def fetch_all_sources() -> List[MovieItem]:
    """Fetch releases from all enabled sources concurrently."""
    tasks = []
    source_names = []

    if ENABLE_MLSBD:
        tasks.append(scrape_mlsbd())
        source_names.append("MLSBD")
    if ENABLE_VEGAMOVIES:
        tasks.append(scrape_vegamovies())
        source_names.append("VegaMovies")
    if ENABLE_FOURKHDHUB:
        tasks.append(scrape_fourkhdhub())
        source_names.append("4K-HDHub")
    if ENABLE_MOVIESMOD:
        tasks.append(scrape_moviesmod())
        source_names.append("MoviesMod")
    if ENABLE_SKYMOVIES:
        tasks.append(scrape_skymovieshd())
        source_names.append("SkyMoviesHD")
    if ENABLE_EXTRAFLIX:
        tasks.append(scrape_extraflix())
        source_names.append("ExtraFlix")
    if ENABLE_HDHUB4U:
        tasks.append(scrape_hdhub4u())
        source_names.append("HDHub4u")
    if ENABLE_KATMOVIEHD:
        tasks.append(scrape_katmoviehd())
        source_names.append("KatMovieHD")
    if ENABLE_KATDRAMA:
        tasks.append(scrape_katdrama())
        source_names.append("KatDrama")
    if ENABLE_DOTMOVIES:
        tasks.append(scrape_dotmovies())
        source_names.append("DotMovies")
    if ENABLE_BOLLYFLIX:
        tasks.append(scrape_bollyflix())
        source_names.append("BollyFlix")
    if ENABLE_CINEVOOD:
        tasks.append(scrape_cinevood())
        source_names.append("CineVood")
    if ENABLE_TOONWORLD:
        tasks.append(scrape_toonworld())
        source_names.append("ToonWorld4All")

    if not tasks:
        LOGGER.warning("No movie sources are enabled in config!")
        return []

    LOGGER.info(f"Running scraper tasks for: {', '.join(source_names)}...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items = []
    for name, res in zip(source_names, results):
        if isinstance(res, Exception):
            LOGGER.error(f"Scraper [{name}] raised exception: {res}")
        elif isinstance(res, list):
            all_items.extend(res)

    LOGGER.info(f"Total collected items from all sources: {len(all_items)}")
    return all_items

