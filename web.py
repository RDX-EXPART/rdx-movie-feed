import logging
import time
from aiohttp import web

from config import PORT
from database import db

LOGGER = logging.getLogger("WebServer")
START_TIME = time.time()


async def handle_root(request):
    total = await db.get_total_count()
    uptime = int(time.time() - START_TIME)
    return web.json_response(
        {
            "status": "online",
            "service": "RDX Movie Feed Bot",
            "total_movies_indexed": total,
            "uptime_seconds": uptime,
        }
    )


async def handle_health(request):
    return web.Response(text="OK", status=200)


def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    return app


async def start_web_server():
    """Start web server for Koyeb & Heroku port binding."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    LOGGER.info(f"Web server started on 0.0.0.0:{PORT} (Health check ready)")
    return runner
