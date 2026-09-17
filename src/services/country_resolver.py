"""Резолвер стран игроков FACEIT — 3 источника + кэш."""
import json
import logging
from pathlib import Path
from curl_cffi import requests as cffi_requests

logger = logging.getLogger("faceit_analytics")


class CountryResolver:
    """Ищет country по нику через несколько источников."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.faceit.com/",
    }

    def __init__(self):
        self._cache = {}
        self._cache_file = Path.cwd() / "data" / "country_cache.json"
        self._load_cache()

    def _load_cache(self):
        if self._cache_file.exists():
            try:
                self._cache = json.loads(
                    self._cache_file.read_text(encoding="utf-8"))
                if logger:
                    logger.info(f"Country cache loaded: "
                                f"{len(self._cache)} записей")
            except Exception:
                self._cache = {}

    def _save_cache(self):
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def get_country(self, nickname):
        if not nickname:
            return ""
        key = nickname.lower()
        if key in self._cache:
            return self._cache[key]

        country = ""
        # Способ 1: users/v1/nicknames
        country = self._try_users_v1(nickname)
        # Способ 2: faceitsync.com
        if not country:
            country = self._try_faceitsync(nickname)
        # Способ 3: FACEIT profile HTML
        if not country:
            country = self._try_profile_html(nickname)

        self._cache[key] = country
        self._save_cache()
        if logger and country:
            logger.debug(f"  {nickname}: {country}")
        return country

    def _try_users_v1(self, nickname):
        try:
            import urllib.parse
            url = (f"https://api.faceit.com/users/v1/nicknames/"
                   f"{urllib.parse.quote(nickname)}")
            r = cffi_requests.get(url, headers=self.HEADERS,
                                   impersonate="safari184", timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Структура может быть в payload или напрямую
                for path in [data.get("payload", {}), data]:
                    if isinstance(path, dict):
                        c = (path.get("country", "") or
                             path.get("country_code", ""))
                        if c:
                            return c.lower()
        except Exception:
            pass
        return ""

    def _try_faceitsync(self, nickname):
        """faceitsync.com — публичные страницы игроков."""
        try:
            import urllib.parse
            # Заменим пробелы на %20
            nick_q = urllib.parse.quote(nickname.replace(" ", "%20"))
            url = f"https://faceitsync.com/en/player/{nick_q}"
            r = cffi_requests.get(url, headers=self.HEADERS,
                                   impersonate="safari184", timeout=15)
            if r.status_code != 200:
                return ""
            html = r.text
            # Ищем паттерны:
            # 1. "country":"ru" или "countryCode":"ru"
            import re
            for pat in [
                    r'"country"\s*:\s*"([a-z]{2})"',
                    r'"countryCode"\s*:\s*"([a-z]{2})"',
                    r'"country_code"\s*:\s*"([a-z]{2})"',
                    r'/flags?/([a-z]{2})\.(?:svg|png)']:
                m = re.search(pat, html, re.I)
                if m:
                    return m.group(1).lower()
            # 2. Флаг может быть в атрибуте alt="ru"
            m = re.search(
                r'<img[^>]*?alt="([a-zA-Z]{2})"[^>]*?>', html)
            if m:
                return m.group(1).lower()
        except Exception:
            pass
        return ""

    def _try_profile_html(self, nickname):
        """Парсит страницу профиля FACEIT."""
        try:
            import urllib.parse
            nick_q = urllib.parse.quote(nickname.replace(" ", "%20"))
            url = f"https://www.faceit.com/ru/players/{nick_q}"
            r = cffi_requests.get(url, headers=self.HEADERS,
                                   impersonate="safari184", timeout=15)
            if r.status_code != 200:
                return ""
            html = r.text
            # Ищем в __NEXT_DATA__ или JSON
            import re
            for pat in [
                    r'"country"\s*:\s*"([a-z]{2})"',
                    r'"countryCode"\s*:\s*"([a-z]{2})"',
                    r'"country_code"\s*:\s*"([a-z]{2})"']:
                m = re.search(pat, html, re.I)
                if m:
                    return m.group(1).lower()
        except Exception:
            pass
        return ""

    def get_all_cached(self):
        return dict(self._cache)


# Глобальный экземпляр
_resolver = None


def get_resolver():
    global _resolver
    if _resolver is None:
        _resolver = CountryResolver()
    return _resolver
