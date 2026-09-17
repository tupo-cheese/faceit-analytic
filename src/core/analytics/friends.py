"""Анализ игр с друзьями."""
from collections import defaultdict
from src.core.analytics.base import BaseAnalyzer


class FriendsAnalyzer(BaseAnalyzer):
    name = "friends"

    def analyze(self, player_steam_id, matches, **kwargs):
        by_friend = defaultdict(list)
        by_combo = defaultdict(list)
        for m in matches:
            friends = m.get("friends_in_team", [])
            for f in friends:
                by_friend[f].append(m)
            combo = "|".join(sorted(friends))
            by_combo[combo].append(m)

        friends_stats = {}
        for f, ms in by_friend.items():
            friends_stats[f] = {
                "matches": len(ms),
                "winrate": self._winrate(ms),
                "avg_kd": self._avg_kd(ms),
                "avg_adr": self._avg(ms, "adr"),
                "avg_rating": self._avg(ms, "rating"),
                "cheaters_against": sum(1 for m in ms if m.get("enemy_cheaters", 0) > 0),
                "cheaters_with": sum(1 for m in ms if m.get("teammate_cheaters", 0) > 0),
            }
        combos_stats = {}
        for combo, ms in by_combo.items():
            combos_stats[combo] = {
                "friends": combo.split("|") if combo else [],
                "matches": len(ms),
                "winrate": self._winrate(ms),
                "avg_kd": self._avg_kd(ms),
                "avg_adr": self._avg(ms, "adr"),
                "avg_rating": self._avg(ms, "rating"),
            }
        return {
            "friends": friends_stats,
            "combinations": combos_stats,
            "total_friends_played_with": len(friends_stats),
        }

    @staticmethod
    def _winrate(ms):
        if not ms:
            return 0.0
        return round(sum(1 for m in ms if m.get("winner") == "A") / len(ms), 3)

    @staticmethod
    def _avg_kd(ms):
        k = sum(m.get("kills", 0) for m in ms)
        d = sum(m.get("deaths", 0) for m in ms)
        return round(k / d, 2) if d else 0.0

    @staticmethod
    def _avg(ms, field):
        vals = [m.get(field, 0) for m in ms if m.get(field)]
        return round(sum(vals) / len(vals), 2) if vals else 0.0
