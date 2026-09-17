"""Leetify API — без ключа (повышенные лимиты)."""
import aiohttp
from src.data_sources.base import DataSource

logger = None


class LeetifySource(DataSource):
    name = "leetify"
    BASE = "https://api-public.cs-prod.leetify.com"

    HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Origin": "https://leetify.com",
        "Referer": "https://leetify.com/",
    }

    def __init__(self, cache, api_key=""):
        self.cache = cache
        self.api_key = api_key
        self.session = None

    async def _session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=30))
        return self.session

    async def fetch_player(self, steam_id):
        """Профиль игрока (без ключа)."""
        cached = self.cache.get("leetify_profile", steam_id)
        if cached:
            return cached
        session = await self._session()
        try:
            async with session.get(
                    f"{self.BASE}/v3/profile",
                    params={"steam64_id": steam_id}) as r:
                if r.status != 200:
                    if logger:
                        logger.debug(f"Leetify profile HTTP {r.status}")
                    return None
                data = await r.json()
            self.cache.set("leetify_profile", steam_id, data)
            return data
        except Exception as e:
            if logger:
                logger.debug(f"Leetify profile: {e}")
            return None

    async def fetch_matches(self, steam_id, limit=50):
        """История матчей (без ключа)."""
        cached = self.cache.get("leetify_matches", steam_id)
        if cached:
            return cached[:limit]
        session = await self._session()
        try:
            async with session.get(
                    f"{self.BASE}/v3/profile/matches",
                    params={"steam64_id": steam_id}) as r:
                if r.status != 200:
                    if logger:
                        logger.debug(f"Leetify matches HTTP {r.status}")
                    return []
                data = await r.json()
            matches = data if isinstance(data, list) else data.get("matches", [])
            if matches:
                self.cache.set("leetify_matches", steam_id, matches)
            if logger:
                logger.info(f"Leetify матчей: {len(matches)}")
            return matches[:limit]
        except Exception as e:
            if logger:
                logger.debug(f"Leetify matches: {e}")
            return []

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
