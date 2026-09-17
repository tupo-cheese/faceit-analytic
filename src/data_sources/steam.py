"""Steam Web API + публичный XML fallback (без ключа)."""
import re
import urllib.request
import aiohttp
from src.data_sources.base import DataSource


class SteamSource(DataSource):
    name = "steam"
    BASE = "https://api.steampowered.com"

    def __init__(self, cache, api_key=""):
        self.cache = cache
        self.api_key = api_key
        self.session = None

    async def _session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "FaceitAnalytics/1.0"})
        return self.session

    async def fetch_player(self, steam_id):
        cached = self.cache.get("steam_player", steam_id)
        if cached:
            return cached

        result = None

        # 1) Если есть ключ — пробуем официальный API
        if self.api_key:
            result = await self._fetch_via_api(steam_id)

        # 2) Если ключа нет или API не дал результата — XML fallback
        if not result:
            result = self._fetch_via_xml(steam_id)

        if result:
            self.cache.set("steam_player", steam_id, result)
        return result

    async def _fetch_via_api(self, steam_id):
        session = await self._session()
        url = f"{self.BASE}/ISteamUser/GetPlayerSummaries/v2/"
        params = {"key": self.api_key, "steamids": steam_id}
        try:
            async with session.get(url, params=params) as r:
                if r.status != 200:
                    return None
                data = await r.json()
            players = data.get("response", {}).get("players", [])
            if not players:
                return None
            p = players[0]
            return {
                "steam_id": p.get("steamid", ""),
                "nickname": p.get("personaname", ""),
                "avatar_url": p.get("avatarfull", ""),
                "steam_url": p.get("profileurl", ""),
                "country": p.get("loccountrycode", ""),
                "visibility": p.get("communityvisibilitystate", 0),
            }
        except Exception:
            return None

    def _fetch_via_xml(self, steam_id):
        """Публичный endpoint без ключа."""
        url = f"https://steamcommunity.com/profiles/{steam_id}/?xml=1"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 FaceitAnalytics/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

        def get_tag(tag):
            m = re.search(f"<{tag}>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</{tag}>", xml, re.S)
            return m.group(1).strip() if m else ""

        return {
            "steam_id": steam_id,
            "nickname": get_tag("steamID"),
            "avatar_url": get_tag("avatarFull"),
            "steam_url": get_tag("steamID64") and f"https://steamcommunity.com/profiles/{steam_id}" or "",
            "country": "",
            "visibility": int(get_tag("visibilityState") or 0),
        }

    async def fetch_matches(self, steam_id, limit=50):
        return []

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
