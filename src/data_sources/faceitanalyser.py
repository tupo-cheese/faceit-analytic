"""Faceit Analyser API — профиль, матчи, статистика."""
import aiohttp
import logging
from src.data_sources.base import DataSource

logger = None


class FaceitAnalyserSource(DataSource):
    name = "faceitanalyser"
    BASE = "https://faceitanalyser.com/api"

    def __init__(self, cache, api_key=""):
        self.cache = cache
        self.api_key = api_key
        self.session = None

    async def _session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30))
        return self.session

    async def fetch_player(self, steam_id, nickname=""):
        """Профиль игрока через Faceit Analyser API."""
        if not self.api_key:
            if logger:
                logger.warning("FaceitAnalyser: нет ключа")
            return None
        cached = self.cache.get("fa_player", steam_id)
        if cached:
            return cached
        # Нужен ник для API
        if not nickname:
            try:
                from curl_cffi import requests as cffi
                r = cffi.get(
                    f"https://steamgpt.net/faceit/{steam_id}.json",
                    impersonate="chrome120", timeout=20)
                if r.status_code == 200:
                    nickname = r.json().get("data", {}).get(
                        "faceit", {}).get("nickname", "")
            except Exception:
                pass
        if not nickname:
            return None
        session = await self._session()
        try:
            url = f"{self.BASE}/stats/{nickname}/cs2"
            async with session.get(url, params={"key": self.api_key}) as r:
                if r.status != 200:
                    if logger:
                        logger.debug(f"FA stats HTTP {r.status}")
                    return None
                data = await r.json()
            self.cache.set("fa_player", steam_id, data)
            if logger:
                logger.info(f"FA stats: {list(data.keys())[:10]}")
            return data
        except Exception as e:
            if logger:
                logger.debug(f"FA stats: {e}")
            return None

    async def fetch_matches(self, steam_id, limit=30, nickname=""):
        """История матчей через Faceit Analyser API."""
        if not self.api_key:
            return []
        cached = self.cache.get("fa_matches", steam_id)
        if cached:
            return cached[:limit]
        if not nickname:
            try:
                from curl_cffi import requests as cffi
                r = cffi.get(
                    f"https://steamgpt.net/faceit/{steam_id}.json",
                    impersonate="chrome120", timeout=20)
                if r.status_code == 200:
                    nickname = r.json().get("data", {}).get(
                        "faceit", {}).get("nickname", "")
            except Exception:
                pass
        if not nickname:
            return []
        session = await self._session()
        try:
            url = f"{self.BASE}/matches/{nickname}/cs2"
            async with session.get(url, params={"key": self.api_key}) as r:
                if r.status != 200:
                    return []
                data = await r.json()
            matches = data.get("matches", [])
            self.cache.set("fa_matches", steam_id, matches)
            if logger:
                logger.info(f"FA matches: {len(matches)}")
            return matches[:limit]
        except Exception as e:
            if logger:
                logger.debug(f"FA matches: {e}")
            return []

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
