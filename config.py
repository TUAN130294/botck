# -*- coding: utf-8 -*-
"""
config.py — cấu hình trung tâm (có hỗ trợ override bằng config_local.json)
"""

import os, json
from pathlib import Path
import pytz

# ========= TIMEZONE =========
TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ========= .env =========
from dotenv import load_dotenv, find_dotenv
_env_loaded = False
ENV_FILE = Path(__file__).resolve().with_name(".env")
if ENV_FILE.exists():
    _env_loaded = load_dotenv(dotenv_path=str(ENV_FILE))
else:
    alt = find_dotenv(filename=".env", usecwd=True)
    if alt:
        _env_loaded = load_dotenv(alt)

# ========= TOKEN & AI =========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "").strip()
FINNHUB_API_KEY    = os.getenv("FINNHUB_API_KEY", "").strip() # MỚI

# Có thể để rỗng, code sẽ dùng mặc định
_raw_urls = os.getenv("GEMINI_BASE_URLS", "").strip()
GEMINI_BASE_URLS = [u.strip().rstrip("/") for u in _raw_urls.split(",") if u.strip()] or [
    "https://api.key4u.shop",
    "https://api2.key4u.shop",
]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ========= BOT/ADMIN =========
ADMIN_IDS  = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip().lstrip("-").isdigit()]
STATUS_PORT = int(os.getenv("STATUS_PORT", "8088"))
HEARTBEAT_CHAT_IDS = os.getenv("HEARTBEAT_CHAT_IDS", "").replace(";", ",")

TARGET_CHAT_IDS = []
for tok in [t.strip() for t in HEARTBEAT_CHAT_IDS.split(",") if t.strip()]:
    if tok.lstrip("-").isdigit():
        TARGET_CHAT_IDS.append(int(tok))

# ========= TA/DATA =========
NEAR_EPS = 0.02
CACHE_TTL = 300
CHART_DAYS = 30
CHART_WIDTH = 800
CHART_HEIGHT = 600
CHART_THEME = "plotly_white"
CHART_FONT = "Arial"

# ========= MONITORING =========
MONITOR_HW_INTERVAL = 60
MONITOR_PENDING_INTERVAL = 120
HEARTBEAT_INTERVAL = 300

# ========= PORTFOLIO =========
MAX_TICKERS_PER_BATCH = 50
NEAR_LEVEL_PERCENTAGE = 1.0

# ========= NEWS =========
NEWS_AUTO_SCHEDULE = True
NEWS_AUTO_IMPACT = True
NEWS_SOURCES = ["cafef", "vietstock", "ndh"]

# ========= REVIEW =========
REVIEW_BRIEF_DEFAULT = False
REVIEW_INCLUDE_AI = True
REVIEW_SHOW_PLAN = False

# ========= LOCAL OVERRIDES =========
def _apply_local_overrides():
    """Apply local configuration overrides from config_local.json"""
    try:
        config_file = Path(__file__).resolve().with_name("config_local.json")
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                obj = json.load(f)
            global NEAR_EPS, CACHE_TTL, CHART_DAYS, CHART_WIDTH, CHART_HEIGHT
            global CHART_THEME, CHART_FONT, REVIEW_BRIEF_DEFAULT, REVIEW_INCLUDE_AI, REVIEW_SHOW_PLAN
            global MAX_TICKERS_PER_BATCH, NEAR_LEVEL_PERCENTAGE
            NEAR_EPS                 = float(obj.get("NEAR_EPS", NEAR_EPS))
            CACHE_TTL                = int(obj.get("CACHE_TTL", CACHE_TTL))
            CHART_DAYS               = int(obj.get("CHART_DAYS", CHART_DAYS))
            CHART_WIDTH              = int(obj.get("CHART_WIDTH", CHART_WIDTH))
            CHART_HEIGHT             = int(obj.get("CHART_HEIGHT", CHART_HEIGHT))
            CHART_THEME              = str(obj.get("CHART_THEME", CHART_THEME))
            CHART_FONT               = str(obj.get("CHART_FONT", CHART_FONT))
            REVIEW_BRIEF_DEFAULT     = bool(obj.get("REVIEW_BRIEF_DEFAULT", REVIEW_BRIEF_DEFAULT))
            REVIEW_INCLUDE_AI        = bool(obj.get("REVIEW_INCLUDE_AI", REVIEW_INCLUDE_AI))
            REVIEW_SHOW_PLAN         = bool(obj.get("REVIEW_SHOW_PLAN", REVIEW_SHOW_PLAN))
            MAX_TICKERS_PER_BATCH    = int(obj.get("MAX_TICKERS_PER_BATCH", MAX_TICKERS_PER_BATCH))
            NEAR_LEVEL_PERCENTAGE    = float(obj.get("NEAR_LEVEL_PERCENTAGE", NEAR_LEVEL_PERCENTAGE))
    except Exception:
        pass

_apply_local_overrides()
