"""
Configuration settings for Manga Video Automation
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
# Note: OUTPUT_DIR is created lazily by pipeline when needed, not on import

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# OpenRouter settings
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
VISION_MODEL = "google/gemini-2.5-flash"  # $0.30/1M, better character recognition

# MangaDex settings
MANGADEX_API_BASE = "https://api.mangadex.org"
MANGADEX_USER_AGENT = "MangaVideoAutomation/1.0"

# Video settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # Portrait for shorts
FPS = 30
DEFAULT_PAGE_DURATION = 4.0  # seconds per page

# Ken Burns effect settings
ZOOM_RANGE = (1.0, 1.15)  # Start and end zoom
PAN_RANGE = 0.05  # Max pan as percentage of image

# Subtitle settings
SUBTITLE_FONT_SIZE = 42
SUBTITLE_MARGIN_BOTTOM = 100
SUBTITLE_BG_OPACITY = 0.7

# Music settings
MUSIC_VOLUME = 0.3  # Background music volume (0-1)
