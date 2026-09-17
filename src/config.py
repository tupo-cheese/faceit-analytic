"""Конфигурация приложения."""
from pathlib import Path
from dataclasses import dataclass

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PLAYERS_DIR = DATA_DIR / "players"
MATCHES_DIR = DATA_DIR / "matches"
EXPORTS_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "faceit_analytics.db"

for p in (DATA_DIR, PLAYERS_DIR, MATCHES_DIR, EXPORTS_DIR, CACHE_DIR):
    p.mkdir(parents=True, exist_ok=True)


@dataclass
class AppSettings:
    steam_api_key: str = ""
    faceit_api_key: str = ""
    leetify_api_key: str = ""
    faceitanalyser_api_key: str = ""      # ← вставь сюда ключ от FA
    parse_bot_api_key: str = ""           # ← вставь сюда ключ от Parse.bot
    max_concurrent_requests: int = 20
    request_timeout: int = 30
    cache_ttl_hours: int = 24 * 7
    theme: str = "dark"


SETTINGS = AppSettings()

COLORS = {
    "bg_primary": "#1a1a1a",
    "bg_secondary": "#1e1e1e",
    "bg_tertiary": "#232323",
    "border": "#2a2a2a",
    "text_primary": "#e8e8e8",
    "text_secondary": "#888888",
    "accent": "#4d6bfe",
    "success": "#3fb950",
    "warning": "#d29922",
    "danger": "#f85149",
    "purple": "#bc8cff",
}

ELO_BRACKET_STEP = 50
