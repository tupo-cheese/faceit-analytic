"""FACEIT stats — корректная формула Rating."""
import json
import logging
from pathlib import Path
from curl_cffi import requests as cffi_requests

logger = logging.getLogger("faceit_analytics")


class FaceitMatchStats:
    BASE = "https://api.faceit.com/stats/v1/stats"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.faceit.com/",
        "Origin": "https://www.faceit.com",
    }

    @classmethod
    def _get_country(cls, nickname):
        try:
            from src.services.country_resolver import get_resolver
            return get_resolver().get_country(nickname)
        except Exception:
            return ""

    @classmethod
    def fetch_raw(cls, match_id):
        url = f"{cls.BASE}/matches/{match_id}"
        try:
            r = cffi_requests.get(url, headers=cls.HEADERS,
                                   impersonate="safari184", timeout=20)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    @classmethod
    def fetch_match(cls, match_id, with_country=True):
        data = cls.fetch_raw(match_id)
        if not data:
            return []
        players = cls._extract_players(data)
        if with_country:
            for p in players:
                nick = p.get("nickname", "")
                if nick and not p.get("country"):
                    p["country"] = cls._get_country(nick)
        return players

    @classmethod
    def _extract_players(cls, data):
        players = []
        item = None
        if isinstance(data, list):
            if not data:
                return []
            item = data[0]
        elif isinstance(data, dict):
            item = data
        if not isinstance(item, dict):
            return []
        teams = item.get("teams")
        if isinstance(teams, list):
            for team in teams:
                faction = team.get("teamId", team.get("faction", ""))
                for p in team.get("players", []) or []:
                    players.append(cls._map_player(p, faction))
        elif isinstance(teams, dict):
            for faction, team in teams.items():
                for p in team.get("players", []) or []:
                    players.append(cls._map_player(p, faction))
        seen = set()
        unique = []
        for p in players:
            k = p.get("player_id") or p.get("nickname")
            if k and k not in seen:
                seen.add(k)
                unique.append(p)
        return unique

    @staticmethod
    def _map_player(p, faction=""):
        def to_int(v):
            try: return int(v)
            except Exception: return 0
        def to_float(v):
            try: return float(v)
            except Exception: return 0.0

        kills = to_int(p.get("i6", 0))
        deaths = to_int(p.get("i8", 0))
        assists = to_int(p.get("i7", 0))
        kd = to_float(p.get("c2", 0))
        kr = to_float(p.get("c3", 0))  # доля, не %
        hs_pct = to_float(p.get("c4", 0))
        adr = to_float(p.get("c10", 0))
        mvps = to_int(p.get("i9", 0))
        headshots = to_int(p.get("i13", 0))
        triple = to_int(p.get("i14", 0))
        quadro = to_int(p.get("i15", 0))
        penta = to_int(p.get("i16", 0))
        rounds = to_int(p.get("i28", 0))
        result = to_int(p.get("i10", 0))

        if kd == 0.0 and deaths:
            kd = round(kills / deaths, 2)

        # ── Rating (HLTV 2.0 приблизительно) ──
        # KAST оцениваем по MVPs и multi-kills
        kast_est = 60 + min(mvps * 3, 12) + min(
            (triple + quadro + penta) * 2, 8)
        kast_est = min(80, max(55, kast_est))
        # Формула: 0.0073*KAST + 0.3591*K/D + 0.5329*K/R
        rating = (0.0073 * kast_est +
                  0.3591 * kd +
                  0.5329 * kr)  # KR уже в долях, не умножаем!
        # Границы реалистичного диапазона
        rating = round(max(0.3, min(1.8, rating)), 2)

        # ── Swing: отклонение rating от 1.0 в % ──
        swing = round((rating - 1.0) * 100, 2) if rating else 0.0

        return {
            "player_id": p.get("playerId") or p.get("player_id", ""),
            "nickname": p.get("nickname", ""),
            "avatar": p.get("avatar", ""),
            "faction": faction,
            "country": p.get("country", ""),
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "kd_ratio": kd,
            "kr_ratio": kr,
            "adr": adr,
            "headshots": headshots,
            "headshots_percent": hs_pct,
            "mvps": mvps,
            "triple_kills": triple,
            "quadro_kills": quadro,
            "penta_kills": penta,
            "rounds": rounds,
            "rating": rating,
            "swing": swing,
            "result": result,
        }
