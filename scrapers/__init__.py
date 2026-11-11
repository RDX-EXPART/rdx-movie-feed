import asyncio
import logging
from typing import List

from config import (
    ENABLE_FOURKHDHUB,
    ENABLE_MLSBD,
    ENABLE_MOVIESMOD,
    ENABLE_SKYMOVIES,
    ENABLE_VEGAMOVIES,
)
from scrapers.base import MovieItem
from scrapers.fourkhdhub import scrape_fourkhdhub
from scrapers.mlsbd import scrape_mlsbd
from scrapers.moviesmod import scrape_moviesmod
from scrapers.skymovieshd import scrape_skymovieshd
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
