"""Сводки по ELO-диапазонам."""
from collections import defaultdict
import statistics
from src.core.analytics.base import BaseAnalyzer


class EloBracketsAnalyzer(BaseAnalyzer):
    name = "elo_brackets"

    def analyze(self, matches, **kwargs):
        brackets = defaultdict(list)
        for m in matches:
            br = m.get("avg_elo_bracket") or 0
            if br:
                brackets[br].append(m)
        out = {}
        for br, ms in sorted(brackets.items()):
            teammates = [m for m in ms if m.get("is_teammate")]
            enemies = [m for m in ms if not m.get("is_teammate")]
            out[br] = {
                "matches": len(ms),
                "avg_stats": self._aggregate(ms),
                "teammates_stats": self._aggregate(teammates) if teammates else {},
                "enemies_stats": self._aggregate(enemies) if enemies else {},
            }
        return out

    @staticmethod
    def _aggregate(matches):
        if not matches:
            return {}
        kills = [m.get("kills", 0) for m in matches]
        deaths = [m.get("deaths", 0) for m in matches]
        assists = [m.get("assists", 0) for m in matches]
        adr = [m.get("adr", 0) for m in matches]
        rating = [m.get("rating", 0) for m in matches]
        kd = [(k / d) if d else 0 for k, d in zip(kills, deaths)]

        def med(v):
            return round(statistics.median(v), 2) if v else 0.0

        return {
            "kills_median": med(kills),
            "deaths_median": med(deaths),
            "assists_median": med(assists),
            "kd_median": med(kd),
            "adr_median": med(adr),
            "rating_median": med(rating),
            "kd_mean": round(sum(kd) / len(kd), 2) if kd else 0.0,
            "adr_mean": round(sum(adr) / len(adr), 1) if adr else 0.0,
        }
