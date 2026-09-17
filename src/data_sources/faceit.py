"""FACEIT — публичный API без ключа + 100 матчей."""
import json
from curl_cffi import requests as cffi_requests
from src.data_sources.base import DataSource


class FaceitSource(DataSource):
    name = "faceit"
    CORE = "https://api.faceit.com/core/v1"
    STATS = "https://api.faceit.com/stats/v1"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": "https://www.faceit.com/",
        "Origin": "https://www.faceit.com",
    }
    LANG_MAP = {"ru": "ru", "uk": "ru", "kz": "ru", "by": "ru",
                "de": "de", "fr": "fr", "es": "es", "it": "it",
                "pt": "pt", "tr": "tr", "pl": "pl", "en": "en"}

    def __init__(self, cache, api_key=""):
        self.cache = cache
        self.api_key = api_key

    def _get_json(self, url, params=None):
        for profile in ["chrome120", "chrome124", "safari184"]:
            try:
                r = cffi_requests.get(
                    url, params=params, headers=self.HEADERS,
                    impersonate=profile, timeout=25)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        pass
            except Exception:
                continue
        return None

    async def fetch_player(self, steam_id):
        cached = self.cache.get("faceit_player", steam_id)
        if cached:
            return cached
        base = {}
        try:
            r = cffi_requests.get(
                f"https://steamgpt.net/faceit/{steam_id}.json",
                impersonate="chrome124", timeout=20)
            if r.status_code == 200:
                data = r.json()
                if data.get("result") == "success":
                    faceit = data.get("data", {}).get("faceit", {})
                    nick = faceit.get("nickname", "")
                    country = (faceit.get("country", "") or "").lower()
                    games = faceit.get("games", {}) or {}
                    cs2 = games.get("cs2") or games.get("CS2") or {}
                    lang = self.LANG_MAP.get(country, "en")
                    base = {
                        "steam_id": steam_id,
                        "faceit_id": faceit.get("player_id", ""),
                        "nickname": nick,
                        "avatar_url": faceit.get("avatar", ""),
                        "country": country,
                        "faceit_url": f"https://www.faceit.com/{lang}/players/{nick}",
                        "faceit_level": cs2.get("skill_level", 0),
                        "faceit_elo": cs2.get("faceit_elo", 0),
                        "faceit_region": cs2.get("region", ""),
                        "faceit_banned": bool(faceit.get("bans")),
                    }
        except Exception:
            pass

        pid = base.get("faceit_id", "")
        if pid:
            stats = self._get_json(f"{self.CORE}/players/{pid}/stats/cs2")
            if stats and "lifetime" in stats:
                lt = stats["lifetime"]
                base["matches_total"] = lt.get("Matches", "—")
                base["win_rate"] = lt.get("Win Rate %", "—")
                base["avg_kd"] = lt.get("Average K/D Ratio", "—")
                base["avg_hs"] = lt.get("Average Headshots %", "—")
                base["recent_results"] = lt.get("Recent Results", [])
                base["current_win_streak"] = lt.get("Current Win Streak", 0)
                base["longest_win_streak"] = lt.get("Longest Win Streak", "—")

        self.cache.set("faceit_player", steam_id, base)
        return base

    def _parse_match(self, m):
        def to_int(v):
            try: return int(v)
            except Exception: return 0
        def to_float(v):
            try: return float(v)
            except Exception: return 0.0
        def to_str(v):
            return str(v) if v is not None else ""

        mid = m.get("matchId") or m.get("match_id") or ""
        kills = to_int(m.get("i6", 0))
        deaths = to_int(m.get("i8", 0))
        assists = to_int(m.get("i7", 0))
        rounds = to_int(m.get("i12", 0))
        result_raw = to_int(m.get("i10", 0))
        score_raw = to_str(m.get("i18", ""))
        score_a, score_b = 0, 0
        if " / " in score_raw:
            parts = score_raw.split(" / ")
            try:
                score_a, score_b = int(parts[0]), int(parts[1])
            except Exception:
                pass
        entry = {
            "match_id": mid,
            "id": mid,
            "source": "faceit",
            "game": m.get("game", "cs2"),
            "date": to_int(m.get("date", 0)),
            "created_at": to_int(m.get("created_at", 0)),
            "elo": to_int(m.get("elo", 0)),
            "elo_delta": to_int(m.get("elo_delta", 0)),
            "region": to_str(m.get("i0", "")),
            "map_name": to_str(m.get("i1", "")),
            "result": result_raw,
            "score_a": score_a,
            "score_b": score_b,
            "score_raw": score_raw,
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "rounds": rounds,
            "mvps": to_int(m.get("i9", 0)),
            "triple_kills": to_int(m.get("i14", 0)),
            "quadro_kills": to_int(m.get("i15", 0)),
            "penta_kills": to_int(m.get("i16", 0)),
            "total_damage": to_int(m.get("i20", 0)),
            "headshots_percent": to_float(m.get("c4", 0)),
            "kd_ratio": to_float(m.get("c2", 0)),
            "kr_ratio": to_float(m.get("c3", 0)),
            "adr": to_float(m.get("c10", 0)),
            "nickname": to_str(m.get("nickname", "")),
            "playerId": to_str(m.get("playerId", "")),
            "premade": bool(m.get("premade", False)),
        }
        if entry["kd_ratio"] == 0.0 and deaths:
            entry["kd_ratio"] = round(kills / deaths, 2)
        return entry

    async def fetch_matches(self, steam_id, limit=100):
        """Загружает до 100 матчей FACEIT."""
        cached = self.cache.get("faceit_matches", steam_id)
        if cached and len(cached) >= min(limit, 100):
            return cached[:limit]
        player = await self.fetch_player(steam_id)
        if not player or not player.get("faceit_id"):
            return []
        pid = player["faceit_id"]
        limit = min(limit, 100)

        url = f"{self.STATS}/stats/time/users/{pid}/games/cs2"
        # FACEIT принимает size до 100
        data = self._get_json(url, params={"size": limit, "page": 0})
        if not data:
            return []
        if isinstance(data, dict):
            data = data.get("items", data.get("data", []))

        matches = []
        for m in data[:limit]:
            entry = self._parse_match(m)
            if entry.get("match_id"):
                matches.append(entry)

        self.cache.set("faceit_matches", steam_id, matches)
        return matches

    async def close(self):
        pass
