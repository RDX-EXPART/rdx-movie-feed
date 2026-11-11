import os
from dotenv import load_dotenv

load_dotenv()


def _bool(val: str, default: bool = True) -> bool:
    if val is None or val == "":
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def _int(val: str, default: int) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# Telegram Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
if CHANNEL_ID and CHANNEL_ID.lstrip("-").isdigit():
    CHANNEL_ID = int(CHANNEL_ID)

# Optional bot username for Leech button (e.g., 'RDX_Leech_Bot')
LEECH_BOT_USERNAME = os.environ.get("LEECH_BOT_USERNAME", "").strip().lstrip("@")

# Check interval in seconds (Default: 300 seconds = 5 minutes)
CHECK_INTERVAL = _int(os.environ.get("CHECK_INTERVAL", "300"), 300)

# Database: MongoDB URL for persistent storage across Heroku/Koyeb restarts
# If empty, a local SQLite database (data/history.db) will be used.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Admin IDs for bot commands (comma-separated user IDs)
raw_admins = os.environ.get("ADMIN_IDS", "").strip()
ADMIN_IDS = [int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()]

# Web server port for Koyeb / Heroku health check
PORT = _int(os.environ.get("PORT", "8080"), 8080)

# Website Domains / RSS Feeds
MLSBD_FEED = os.environ.get("MLSBD_FEED", "https://mlsbd.co/feed/").strip()
VEGAMOVIES_URL = os.environ.get("VEGAMOVIES_URL", "https://vegamovis.skin").strip().rstrip("/")
FOURKHDHUB_URL = os.environ.get("FOURKHDHUB_URL", "https://4khdhub.one").strip().rstrip("/")
MOVIESMOD_URL = os.environ.get("MOVIESMOD_URL", "https://moviesmod.tw").strip().rstrip("/")
SKYMOVIES_URL = os.environ.get("SKYMOVIES_URL", "https://skymovieshd.green").strip().rstrip("/")

# Source Toggles
ENABLE_MLSBD = _bool(os.environ.get("ENABLE_MLSBD", "true"))
ENABLE_VEGAMOVIES = _bool(os.environ.get("ENABLE_VEGAMOVIES", "true"))
ENABLE_FOURKHDHUB = _bool(os.environ.get("ENABLE_FOURKHDHUB", "true"))
ENABLE_MOVIESMOD = _bool(os.environ.get("ENABLE_MOVIESMOD", "true"))
ENABLE_SKYMOVIES = _bool(os.environ.get("ENABLE_SKYMOVIES", "true"))

# On first boot with an empty database, do not spam the channel with past movies.
# Mark existing items as already posted.
INITIAL_MARK_SEEN = _bool(os.environ.get("INITIAL_MARK_SEEN", "true"))
