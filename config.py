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

# Multiple Leech Bots Support (comma-separated usernames, with or without @)
# e.g., 'RDX_Leech_Bot, RDX_VIP_Bot, RDX_Backup_Bot'
raw_leech_bots = os.environ.get("LEECH_BOT_USERNAMES", "").strip() or os.environ.get("LEECH_BOT_USERNAME", "").strip()
LEECH_BOTS = [b.strip().lstrip("@") for b in raw_leech_bots.split(",") if b.strip().lstrip("@")]
LEECH_BOT_USERNAME = LEECH_BOTS[0] if LEECH_BOTS else ""

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
VEGAMOVIES_URL = os.environ.get("VEGAMOVIES_URL", "").strip().rstrip("/")
FOURKHDHUB_URL = os.environ.get("FOURKHDHUB_URL", "https://4khdhub.one").strip().rstrip("/")
MOVIESMOD_URL = os.environ.get("MOVIESMOD_URL", "").strip().rstrip("/")
SKYMOVIES_URL = os.environ.get("SKYMOVIES_URL", "").strip().rstrip("/")
EXTRAFLIX_URL = os.environ.get("EXTRAFLIX_URL", "").strip().rstrip("/")
HDHUB4U_URL = os.environ.get("HDHUB4U_URL", "").strip().rstrip("/")
KATMOVIEHD_URL = os.environ.get("KATMOVIEHD_URL", "").strip().rstrip("/")
KATDRAMA_URL = os.environ.get("KATDRAMA_URL", "").strip().rstrip("/")
DOTMOVIES_URL = os.environ.get("DOTMOVIES_URL", "").strip().rstrip("/")
BOLLYFLIX_URL = os.environ.get("BOLLYFLIX_URL", "").strip().rstrip("/")
CINEVOOD_URL = os.environ.get("CINEVOOD_URL", "").strip().rstrip("/")
TOONWORLD_URL = os.environ.get("TOONWORLD_URL", "").strip().rstrip("/")

# Domain Announcement Hubs (Auto-detection for rotating domains)
VEGA_HUB_URL = os.environ.get("VEGA_HUB_URL", "https://1vegamovies.buzz").strip().rstrip("/")
MODLIST_HUB_URL = os.environ.get("MODLIST_HUB_URL", "https://www.modlist.in/?type=hollywood").strip().rstrip("/")
SKYBAP_URL = os.environ.get("SKYBAP_URL", "https://skybap.site").strip().rstrip("/")
EXTRAFLIX_HUB_URL = os.environ.get("EXTRAFLIX_HUB_URL", "https://extraflix.foo").strip().rstrip("/")
HDHUB4U_HUB_URL = os.environ.get("HDHUB4U_HUB_URL", "https://hdhub4u.deal").strip().rstrip("/")
KATMOVIEHD_HUB_URL = os.environ.get("KATMOVIEHD_HUB_URL", "https://katmovieshd.net").strip().rstrip("/")
DOTMOVIES_HUB_URL = os.environ.get("DOTMOVIES_HUB_URL", "https://dotmovies.army").strip().rstrip("/")
BOLLYFLIX_HUB_URL = os.environ.get("BOLLYFLIX_HUB_URL", "https://bollyflix.baby").strip().rstrip("/")
CINEVOOD_HUB_URL = os.environ.get("CINEVOOD_HUB_URL", "https://cinevood.garden").strip().rstrip("/")

# Source Toggles
ENABLE_MLSBD = _bool(os.environ.get("ENABLE_MLSBD", "true"))
ENABLE_VEGAMOVIES = _bool(os.environ.get("ENABLE_VEGAMOVIES", "true"))
ENABLE_FOURKHDHUB = _bool(os.environ.get("ENABLE_FOURKHDHUB", "true"))
ENABLE_MOVIESMOD = _bool(os.environ.get("ENABLE_MOVIESMOD", "true"))
ENABLE_SKYMOVIES = _bool(os.environ.get("ENABLE_SKYMOVIES", "true"))
ENABLE_EXTRAFLIX = _bool(os.environ.get("ENABLE_EXTRAFLIX", "true"))
ENABLE_HDHUB4U = _bool(os.environ.get("ENABLE_HDHUB4U", "true"))
ENABLE_KATMOVIEHD = _bool(os.environ.get("ENABLE_KATMOVIEHD", "true"))
ENABLE_KATDRAMA = _bool(os.environ.get("ENABLE_KATDRAMA", "true"))
ENABLE_DOTMOVIES = _bool(os.environ.get("ENABLE_DOTMOVIES", "true"))
ENABLE_BOLLYFLIX = _bool(os.environ.get("ENABLE_BOLLYFLIX", "true"))
ENABLE_CINEVOOD = _bool(os.environ.get("ENABLE_CINEVOOD", "true"))
ENABLE_TOONWORLD = _bool(os.environ.get("ENABLE_TOONWORLD", "true"))

# On first boot with an empty database, do not spam the channel with past movies.
# Mark existing items as already posted.
INITIAL_MARK_SEEN = _bool(os.environ.get("INITIAL_MARK_SEEN", "true"))
