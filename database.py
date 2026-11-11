import asyncio
import logging
import os
import sqlite3
import time
from typing import Optional

from config import DATABASE_URL

LOGGER = logging.getLogger("Database")


class FeedDatabase:
    def __init__(self, db_url: str = ""):
        self.db_url = db_url or DATABASE_URL
        self.use_mongo = False
        self.mongo_client = None
        self.collection = None
        self.sqlite_path = os.path.join(os.path.dirname(__file__), "data", "history.db")
        self._init_db()

    def _init_db(self):
        if self.db_url and self.db_url.startswith(("mongodb://", "mongodb+srv://")):
            try:
                import pymongo

                self.mongo_client = pymongo.MongoClient(
                    self.db_url,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                )
                # Test connection
                self.mongo_client.admin.command("ping")
                db = self.mongo_client["rdx_movie_feed"]
                self.collection = db["posted_movies"]
                self.collection.create_index("url", unique=True)
                self.use_mongo = True
                LOGGER.info("Connected to MongoDB successfully for persistent storage.")
                return
            except Exception as e:
                LOGGER.warning(f"MongoDB connection failed: {e}. Falling back to SQLite.")
                self.use_mongo = False

        # SQLite fallback
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS posted_movies (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    site TEXT,
                    timestamp REAL
                )
            """
            )
            conn.commit()
        LOGGER.info(f"Initialized SQLite database at {self.sqlite_path}")

    def _is_seen_sync(self, url: str) -> bool:
        if not url:
            return True
        norm_url = url.strip()
        if self.use_mongo:
            try:
                return bool(self.collection.find_one({"url": norm_url}))
            except Exception as e:
                LOGGER.error(f"MongoDB is_seen error: {e}")
                return False
        else:
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM posted_movies WHERE url = ? LIMIT 1", (norm_url,))
                    return cursor.fetchone() is not None
            except Exception as e:
                LOGGER.error(f"SQLite is_seen error: {e}")
                return False

    def _mark_seen_sync(self, url: str, title: str = "", site: str = ""):
        if not url:
            return
        norm_url = url.strip()
        now = time.time()
        if self.use_mongo:
            try:
                self.collection.update_one(
                    {"url": norm_url},
                    {"$set": {"url": norm_url, "title": title, "site": site, "timestamp": now}},
                    upsert=True,
                )
            except Exception as e:
                LOGGER.error(f"MongoDB mark_seen error: {e}")
        else:
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO posted_movies (url, title, site, timestamp)
                        VALUES (?, ?, ?, ?)
                    """,
                        (norm_url, title, site, now),
                    )
                    conn.commit()
            except Exception as e:
                LOGGER.error(f"SQLite mark_seen error: {e}")

    def _get_count_sync(self) -> int:
        if self.use_mongo:
            try:
                return self.collection.count_documents({})
            except Exception as e:
                LOGGER.error(f"MongoDB count error: {e}")
                return 0
        else:
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM posted_movies")
                    row = cursor.fetchone()
                    return row[0] if row else 0
            except Exception as e:
                LOGGER.error(f"SQLite count error: {e}")
                return 0

    def _get_recent_sync(self, limit: int = 10) -> list:
        results = []
        if self.use_mongo:
            try:
                cursor = self.collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
                return list(cursor)
            except Exception as e:
                LOGGER.error(f"MongoDB get_recent error: {e}")
                return []
        else:
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT url, title, site, timestamp FROM posted_movies ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    )
                    for r in cursor.fetchall():
                        results.append({"url": r[0], "title": r[1], "site": r[2], "timestamp": r[3]})
                return results
            except Exception as e:
                LOGGER.error(f"SQLite get_recent error: {e}")
                return []

    # Async Wrappers
    async def is_seen(self, url: str) -> bool:
        return await asyncio.to_thread(self._is_seen_sync, url)

    async def mark_seen(self, url: str, title: str = "", site: str = ""):
        await asyncio.to_thread(self._mark_seen_sync, url, title, site)

    async def get_total_count(self) -> int:
        return await asyncio.to_thread(self._get_count_sync)

    async def is_empty(self) -> bool:
        count = await self.get_total_count()
        return count == 0

    async def get_recent(self, limit: int = 10) -> list:
        return await asyncio.to_thread(self._get_recent_sync, limit)


db = FeedDatabase()
