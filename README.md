<h1 align="center">🎬 RDX Movie Feed Bot</h1>

<p align="center">
  <b>High-speed, automated multi-source movie release monitor and Telegram channel auto-poster.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Platform-Koyeb%20%7C%20Heroku%20%7C%20Docker-green.svg" alt="Platforms">
  <img src="https://img.shields.io/badge/Database-MongoDB%20%7C%20SQLite-orange.svg" alt="Database">
  <img src="https://img.shields.io/badge/Telegram-Bot%20API-informational.svg" alt="Telegram Bot API">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey.svg" alt="License">
</p>

---

## 📖 Overview

**RDX Movie Feed Bot** is a lightweight, asynchronous background scraper designed to track the latest movie and web-series uploads from popular release platforms. Whenever a new release is published, the bot automatically formats a Telegram post card featuring the high-resolution poster, title, video resolutions, publication date, direct website links, and an optional **`[📥 Leech via Bot]`** inline button for instant 1-click downloading through your personal Leech Bot.

---

## 🌟 Key Features

- **Multi-Source Scraping**: Concurrently scrapes releases from top entertainment portals:
  - **MLSBD** (Native WordPress XML Feed)
  - **VegaMovies** (Dual Audio, Hindi Dubbed & Web Series)
  - **4K-HDHub** (4K UHD, 2160p, 1080p, HDR & HEVC releases)
  - **MoviesMod** (Latest OTT Series & Regional Movies)
  - **SkyMoviesHD** (Bengali, South Indian Dubbed & Multi-audio)
- **High-Resolution Poster Extraction**: Automatically parses TMDb, CDN, and WordPress media embeds.
- **Intelligent Deduplication**:
  - Remembers published items so the channel is never spammed with duplicates.
  - Initial Boot Guard: On first startup, marks existing catalog items as seen and only broadcasts brand-new releases.
- **Persistent Cloud Database**: Supports **MongoDB Atlas** for persistence across Koyeb / Heroku dyno restarts, with an automatic fallback to local SQLite.
- **Built-in Web Server**: Runs a lightweight HTTP server on `0.0.0.0:$PORT` with `/health` endpoints to keep Koyeb and Heroku health checks alive 24/7.
- **Zero Server Overhead**: Extremely low RAM (< 45MB) and CPU consumption.
- **Admin Control**: Interact directly with the bot via `/status` and `/check` commands.

---

## 🎯 Architecture: Why a Separate Feed Bot?

Running automatic RSS downloads directly inside a heavy download engine (`rdx-technology`) often causes severe bottlenecks:
- When a new title is posted, multiple qualities (`480p`, `720p`, `1080p`, `4K`) or entire seasons (10+ episodes) get queued simultaneously, exhausting disk space, RAM, and bandwidth.
- Telegram frequently issues **FloodWait** penalties when bombarded with multiple simultaneous uploads.

**The Solution:**
**RDX Movie Feed Bot** acts as an ultra-light sentinel. It publishes beautiful preview cards with an **`[📥 Leech via Bot]`** button to your channel. Subscribers or administrators can selectively trigger the download of only the exact resolution they want, keeping server resources completely safe.

---

## 🚀 Deployment Guide

### Prerequisites
1. **Telegram Bot Token**: Get one from [@BotFather](https://t.me/BotFather).
2. **Channel ID**: Add your bot to your Telegram Channel as an **Administrator** with the **"Post Messages"** permission enabled. Note your channel username (e.g., `@MyChannel`) or channel ID (e.g., `-1001234567890`).

---

### Method 1: Deploy to Koyeb (Recommended, Free 24/7)

[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/RDX-EXPART/rdx-movie-feed&branch=main&name=rdx-movie-feed)

1. Sign in to [Koyeb](https://www.koyeb.com/).
2. Click **Create App** and select **GitHub** (or click the button above).
3. Choose the repository: `RDX-EXPART/rdx-movie-feed`.
4. Leave the builder as **Dockerfile** (or Buildpack).
5. Add the following **Environment Variables**:
   | Variable | Value | Description |
   |---|---|---|
   | `BOT_TOKEN` | `123456:ABC-DEF...` | Telegram Bot Token from @BotFather |
   | `CHANNEL_ID` | `-1001234567890` | Target Channel ID or `@Username` |
   | `LEECH_BOT_USERNAME` | `RDX_Leech_Bot` | Optional: Your Leech Bot's username |
   | `DATABASE_URL` | `mongodb+srv://...` | Optional: MongoDB Atlas URI for persistent state |
   | `CHECK_INTERVAL` | `300` | Scrape frequency in seconds (default: 300) |
   | `PORT` | `8080` | Required for Koyeb health check |
6. Click **Deploy**. Your feed bot will be live within 2 minutes!

---

### Method 2: Deploy to Heroku

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/RDX-EXPART/rdx-movie-feed)

1. Create a new app on [Heroku](https://dashboard.heroku.com/).
2. In the **Deploy** tab, connect your GitHub repository `RDX-EXPART/rdx-movie-feed`.
3. In **Settings** -> **Reveal Config Vars**, add:
   - `BOT_TOKEN`
   - `CHANNEL_ID`
   - `LEECH_BOT_USERNAME` (Optional)
   - `DATABASE_URL` (Optional MongoDB URI)
   - `CHECK_INTERVAL` (e.g. `300`)
4. In the **Resources** tab, activate the `web` dyno (`python3 main.py`).

---

### Method 3: Run via Docker

```bash
# Build the Docker image
docker build -t rdx-movie-feed .

# Run the container
docker run -d \
  --name rdx-movie-feed \
  -p 8080:8080 \
  -e BOT_TOKEN="your_bot_token" \
  -e CHANNEL_ID="your_channel_id" \
  -e LEECH_BOT_USERNAME="your_leech_bot_username" \
  rdx-movie-feed
```

---

### Method 4: Local / VPS Setup

```bash
# Clone the repository
git clone https://github.com/RDX-EXPART/rdx-movie-feed.git
cd rdx-movie-feed

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env
nano .env  # Enter your BOT_TOKEN and CHANNEL_ID

# Start the bot
python3 main.py
```

---

## ⚙️ Configuration Reference (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | **Yes** | — | Telegram Bot token from @BotFather |
| `CHANNEL_ID` | **Yes** | — | Telegram Channel ID or `@ChannelUsername` |
| `LEECH_BOT_USERNAMES` | No | — | Leech Bot username(s) separated by comma (e.g. `Bot1, Bot2`) |
| `DATABASE_URL` | No | `""` | MongoDB Atlas URI. If omitted, uses local SQLite |
| `ADMIN_IDS` | No | `""` | Comma-separated admin Telegram user IDs |
| `CHECK_INTERVAL` | No | `300` | Time interval between scrapes (in seconds) |
| `PORT` | No | `8080` | HTTP port for Koyeb/Heroku health-check |
| `VEGAMOVIES_URL` | No | `https://vegamovies.lease` | Primary VegaMovies domain |
| `SKYMOVIES_URL` | No | `""` (Auto) | Manual SkyMoviesHD domain (leave empty to auto-detect from `skybap.site`) |
| `ENABLE_MLSBD` | No | `true` | Toggle MLSBD source |
| `ENABLE_VEGAMOVIES` | No | `true` | Toggle VegaMovies source |
| `ENABLE_FOURKHDHUB` | No | `true` | Toggle 4K-HDHub source |
| `ENABLE_MOVIESMOD` | No | `true` | Toggle MoviesMod source |
| `ENABLE_SKYMOVIES` | No | `true` | Toggle SkyMoviesHD source |
| `INITIAL_MARK_SEEN` | No | `true` | Prevents posting old movies on first startup |

---

## 🤖 Admin Commands & Interactive Control Panel

The bot includes an interactive Menu button and private chat Control Panel:

- `/start` or `/panel` — Opens the interactive Control Panel with inline buttons:
  - `[ 📊 Bot Status ]` — Displays real-time database, channel, and source statistics.
  - `[ 🔄 Check Now ]` — Triggers an instant release scan across all providers.
  - `[ 🌐 Active Domains ]` — Lists all current working provider domains.
  - `[ 🔁 Restart Bot ]` — Gracefully reboots the bot process.
- `/status` — Quick status report.
- `/check` or `/force` — Immediately triggers an on-demand check for new releases.
- `/sources` — Displays current working domains (including auto-detected SkyMoviesHD).
- `/restart` — Gracefully restarts the bot process.

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).
Developed with ❤️ for the **RDX Community**.
