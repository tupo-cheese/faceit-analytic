"""Глубокая аналитика."""
import statistics
from collections import defaultdict


def _median(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else 0.0


def _mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else 0.0


class DeepAnalyzer:
    def analyze(self, player, matches, **kwargs):
        ms = []
        for m in matches:
            if isinstance(m, dict) and "data" in m:
                d = dict(m["data"])
                d.setdefault("elo", m.get("avg_elo", 0))
                ms.append(d)
            else:
                ms.append(m)
        if not ms:
            return self._empty()

        kills = [int(m.get("kills", 0) or 0) for m in ms]
        deaths = [int(m.get("deaths", 0) or 0) for m in ms]
        assists = [int(m.get("assists", 0) or 0) for m in ms]
        kd_list = [float(m.get("kd_ratio", 0) or 0) for m in ms]
        adr = [float(m.get("adr", 0) or 0) for m in ms if m.get("adr")]
        hs = [float(m.get("headshots_percent", 0) or 0) for m in ms
              if m.get("headshots_percent")]
        elos = [int(m.get("elo", 0) or 0) for m in ms if m.get("elo")]
        wins = sum(1 for m in ms if int(m.get("result", 0) or 0) == 1)
        total = len(ms)

        summary = {
            "matches": total,
            "wins": wins,
            "winrate": round(wins / total * 100, 1) if total else 0,
            "kills": sum(kills),
            "deaths": sum(deaths),
            "assists": sum(assists),
            "kd_total": round(sum(kills) / max(sum(deaths), 1), 2),
            "kd_avg": round(_mean(kd_list), 2),
            "kd_median": round(_median(kd_list), 2),
            "adr_avg": round(_mean(adr), 1),
            "adr_median": round(_median(adr), 1),
            "hs_avg": round(_mean(hs), 1),
            "hs_median": round(_median(hs), 1),
            "kills_avg": round(_mean(kills), 1),
            "deaths_avg": round(_mean(deaths), 1),
            "assists_avg": round(_mean(assists), 1),
            "mvps_avg": round(_mean([int(m.get("mvps", 0) or 0) for m in ms]), 2),
            "rounds_avg": round(_mean([int(m.get("rounds", 0) or 0) for m in ms]), 1),
            "elo_avg": round(_mean(elos)) if elos else 0,
            "elo_min": min(elos) if elos else 0,
            "elo_max": max(elos) if elos else 0,
            "elo_delta_sum": sum(int(m.get("elo_delta", 0) or 0) for m in ms),
        }

        # По ELO-бакетам
        brackets = defaultdict(list)
        for m in ms:
            e = int(m.get("elo", 0) or 0)
            if e:
                brackets[(e // 50) * 50].append(m)
        by_elo = {br: self._agg(group) for br, group in brackets.items()}

        # По картам
        maps = defaultdict(list)
        for m in ms:
            maps[m.get("map_name", "unknown")].append(m)
        by_map = {mp: self._agg(group) for mp, group in maps.items()}

        # Прогресс
        progress = self._progress(ms)

        # Аномалии
        anomalies = self._anomalies(ms)

        return {
            "summary": summary,
            "by_elo": by_elo,
            "by_map": by_map,
            "by_month": {},
            "anomalies": anomalies,
            "progress": progress,
            "raw_matches": ms,
        }

    def _agg(self, group):
        kills = [int(m.get("kills", 0) or 0) for m in group]
        deaths = [int(m.get("deaths", 0) or 0) for m in group]
        assists = [int(m.get("assists", 0) or 0) for m in group]
        kd = [float(m.get("kd_ratio", 0) or 0) for m in group]
        adr = [float(m.get("adr", 0) or 0) for m in group if m.get("adr")]
        hs = [float(m.get("headshots_percent", 0) or 0) for m in group
              if m.get("headshots_percent")]
        wins = sum(1 for m in group if int(m.get("result", 0) or 0) == 1)
        elos = [int(m.get("elo", 0) or 0) for m in group if m.get("elo")]
        return {
            "matches": len(group),
            "wins": wins,
            "winrate": round(wins / len(group) * 100, 1) if group else 0,
            "kd_ratio": round(sum(kills) / max(sum(deaths), 1), 2),
            "kd_avg": round(_mean(kd), 2),
            "kd_median": round(_median(kd), 2),
            "kills_avg": round(_mean(kills), 1),
            "deaths_avg": round(_mean(deaths), 1),
            "assists_avg": round(_mean(assists), 1),
            "adr_avg": round(_mean(adr), 1),
            "adr_median": round(_median(adr), 1),
            "hs_avg": round(_mean(hs), 1),
            "hs_median": round(_median(hs), 1),
            "elo_avg": round(_mean(elos)) if elos else 0,
        }

    def _progress(self, ms):
        if len(ms) < 20:
            return {}
        s = sorted(ms, key=lambda m: int(m.get("date", 0) or 0), reverse=True)
        a = self._agg(s[:10])
        b = self._agg(s[10:20])
        return {
            "last_10": a,
            "prev_10": b,
            "winrate_delta": round(a["winrate"] - b["winrate"], 1),
            "kd_delta": round(a["kd_avg"] - b["kd_avg"], 2),
            "adr_delta": round(a["adr_avg"] - b["adr_avg"], 1),
        }

    def _anomalies(self, ms):
        anomalies = []
        adr = [float(m.get("adr", 0) or 0) for m in ms if m.get("adr")]
        if len(adr) >= 10:
            mean = statistics.mean(adr)
            stdev = statistics.pstdev(adr) or 1
            for m in ms:
                a = float(m.get("adr", 0) or 0)
                if a and abs(a - mean) > 2.5 * stdev:
                    anomalies.append({
                        "type": "adr_outlier",
                        "map": m.get("map_name", ""),
                        "value": round(a, 1),
                        "mean": round(mean, 1),
                        "sigma": round((a - mean) / stdev, 2),
                    })
        return anomalies

    def _empty(self):
        return {"summary": {"matches": 0}, "by_elo": {}, "by_map": {},
                "by_month": {}, "anomalies": [], "progress": {},
                "raw_matches": []}
