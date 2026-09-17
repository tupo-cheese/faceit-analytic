"""Сервис управления игроками."""
import asyncio
from src.data_sources.steam import SteamSource
from src.data_sources.faceit import FaceitSource
from src.data_sources.cswatch import CSWatchSource
from src.data_sources.csstats import CSStatsSource
from src.config import SETTINGS


class PlayerService:
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache
        self.steam = SteamSource(cache, SETTINGS.steam_api_key)
        self.faceit = FaceitSource(cache, SETTINGS.faceit_api_key)
        self.cswatch = CSWatchSource(cache)
        self.csstats = CSStatsSource(cache)

    async def fetch_matches(self, steam_id, limit=100):
        """Собираем матчи только с FACEIT (Leetify не работает)."""
        matches = await self.faceit.fetch_matches(steam_id, limit)
        for m in matches:
            m["source"] = "faceit"
        return matches

    async def close(self):
        await self.steam.close()
        await self.faceit.close()
        await self.cswatch.close()
        await self.csstats.close()
