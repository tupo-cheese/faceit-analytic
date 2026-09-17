"""Быстрая аналитика."""
from src.core.analytics.base import BaseAnalyzer


class QuickAnalyzer(BaseAnalyzer):
    name = "quick"

    def analyze(self, player, matches=None, **kwargs):
        matches = matches or []
        kills = sum(m.get("kills", 0) for m in matches)
        deaths = sum(m.get("deaths", 0) for m in matches)
        assists = sum(m.get("assists", 0) for m in matches)
        kd = (kills / deaths) if deaths else 0.0
        adr = (sum(m.get("adr", 0) for m in matches) / len(matches)) if matches else 0.0
        rating = (sum(m.get("rating", 0) for m in matches) / len(matches)) if matches else 0.0
        return {
            "nickname": player.get("nickname", ""),
            "avatar_url": player.get("avatar_url", ""),
            "faceit_level": player.get("faceit_level", 0),
            "faceit_elo": player.get("faceit_elo", 0),
            "premier_rating": player.get("premier_rating", 0),
            "steam_url": player.get("steam_url", ""),
            "faceit_url": player.get("faceit_url", ""),
            "matches_count": len(matches),
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "kd": round(kd, 2),
            "avg_adr": round(adr, 1),
            "avg_rating": round(rating, 2),
            "vac_banned": player.get("vac_banned", False),
        }
