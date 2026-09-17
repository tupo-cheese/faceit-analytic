"""Parse.bot CSStats.gg API — 200 бесплатных кредитов."""
import aiohttp
import logging
from src.data_sources.base import DataSource

logger = None


class ParseBotCSStats(DataSource):
    name = "parse_bot_csstats"
    BASE = "https://api.parse.bot/scraper"
    SCRAPER_ID = "758b30c6-74c7-46ea-a4fb-2efd60740f7c"

    def __init__(self, cache, api_key=""):
        self.cache = cache
        self.api_key = api_key
        self.session = None

    async def _session(self):
        if self.session is None or self.session.closed:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30))
        return self.session

    async def fetch_player(self, steam_id):
        """Профиль игрока через Parse.bot."""
        if not self.api_key:
            if logger:
                logger.warning("Parse.bot: нет ключа")
            return None
        cached = self.cache.get("pb_player", steam_id)
        if cached:
            return cached
        session = await self._session()
        try:
            url = f"{self.BASE}/{self.SCRAPER_ID}/get_player_stats"
            async with session.get(url, params={"steam_id": steam_id}) as r:
                if r.status != 200:
                    return None
                data = await r.json()
            self.cache.set("pb_player", steam_id, data)
            return data
        except Exception as e:
            if logger:
                logger.debug(f"Parse.bot profile: {e}")
            return None

    async def fetch_matches(self, steam_id, limit=50):
        """История матчей через Parse.bot."""
        if not self.api_key:
            return []
        cached = self.cache.get("pb_matches", steam_id)
        if cached:
            return cached[:limit]
        session = await self._session()
        try:
            url = f"{self.BASE}/{self.SCRAPER_ID}/get_player_matches"
            async with session.get(url, params={"steam_id": steam_id}) as r:
                if r.status != 200:
                    return []
                data = await r.json()
            matches = data.get("matches", [])
            self.cache.set("pb_matches", steam_id, matches)
            if logger:
                logger.info(f"Parse.bot matches: {len(matches)}")
            return matches[:limit]
        except Exception as e:
            if logger:
                logger.debug(f"Parse.bot matches: {e}")
            return []

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
