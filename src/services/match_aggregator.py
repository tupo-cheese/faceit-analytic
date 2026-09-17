"""Агрегатор: режим personal (по игроку) и lobby (по среднему)."""
import asyncio
import logging
from collections import defaultdict, Counter

logger = logging.getLogger("faceit_analytics")


class MatchAggregator:
    def __init__(self, cache, db, elo_step=50):
        self.cache = cache
        self.db = db
        self.elo_step = elo_step
        self.on_progress = None

    async def collect_matches(self, matches, my_player_id, limit=50,
                               enrich_countries=True, enrich_elo=True):
        from src.data_sources.faceit_stats import FaceitMatchStats

        results = []
        total = min(len(matches), limit)

        for i, m in enumerate(matches[:limit]):
            mid = m.get("match_id") or m.get("id")
            if not mid:
                continue
            elo = int(m.get("elo", 0) or 0)
            map_name = m.get("map_name", "")
            date = int(m.get("date", 0) or 0)
            result_flag = int(m.get("result", 0) or 0)

            cached = self.cache.get("match_players", mid)
            if cached:
                players = cached
            else:
                players = FaceitMatchStats.fetch_match(
                    mid, with_country=False)
                if players:
                    self.cache.set("match_players", mid, players)
                await asyncio.sleep(0.05)

            if not players:
                continue
            my_faction = None
            my_stats = None
            for p in players:
                if p.get("player_id") == my_player_id:
                    my_faction = p.get("faction")
                    my_stats = p
                    break
            if not my_faction:
                continue
            teammates = [p for p in players
                         if p.get("faction") == my_faction
                         and p.get("player_id") != my_player_id]
            enemies = [p for p in players
                       if p.get("faction") != my_faction]

            results.append({
                "match_id": mid, "elo": elo, "map_name": map_name,
                "date": date, "party_size": len(teammates) + 1,
                "result": result_flag, "my_faction": my_faction,
                "my_stats": my_stats, "teammates": teammates,
                "enemies": enemies,
            })
            if self.on_progress:
                self.on_progress(i + 1, total, f"{i+1}/{total}")

        if enrich_countries:
            try:
                from src.services.country_resolver import get_resolver
                resolver = get_resolver()
                nicks = set()
                for entry in results:
                    for p in entry["teammates"] + entry["enemies"]:
                        n = p.get("nickname", "")
                        if n and not p.get("country"):
                            nicks.add(n)
                for n in nicks:
                    resolver.get_country(n)
                for entry in results:
                    for p in entry["teammates"] + entry["enemies"]:
                        n = (p.get("nickname") or "").lower()
                        if not p.get("country"):
                            p["country"] = resolver._cache.get(n, "")
            except Exception as e:
                logger.warning(f"countries: {e}")

        if enrich_elo:
            try:
                from src.services.player_elo_resolver import (
                    get_elo_resolver)
                resolver = get_elo_resolver()
                nicks = set()
                for entry in results:
                    for p in entry["teammates"] + entry["enemies"]:
                        n = p.get("nickname", "")
                        if n:
                            nicks.add(n)
                elo_map = resolver.batch_get(list(nicks), max_workers=20)
                for entry in results:
                    for p in entry["teammates"] + entry["enemies"]:
                        n = (p.get("nickname") or "").lower()
                        info = elo_map.get(n, {})
                        p["player_elo"] = info.get("elo", 0)
                        p["player_level"] = info.get("level", 0)
                        p["player_winrate"] = info.get("winrate", 0)
            except Exception as e:
                logger.warning(f"elo: {e}")

        return results

    def detect_friends(self, match_data, min_appearances=2):
        c = Counter()
        for entry in match_data:
            for p in entry["teammates"]:
                key = p.get("player_id") or p.get("nickname", "")
                if key:
                    c[key] += 1
        return {k for k, n in c.items() if n >= min_appearances}

    def build_stats_by_elo(self, match_data, elo_step=None,
                            filter_party=None, friends_set=None,
                            filter_countries=None, median_mode=False,
                            elo_mode="personal"):
        """
        elo_mode:
          'personal' — по личному ELO каждого игрока
          'lobby' — по среднему ELO матча
        """
        import statistics
        step = elo_step or self.elo_step
        if friends_set is None:
            friends_set = self.detect_friends(match_data)
        fc = (set(c.lower() for c in filter_countries)
              if filter_countries else None)

        tm_items = defaultdict(list)
        en_items = defaultdict(list)
        fr_items = defaultdict(list)
        pl_items = defaultdict(list)

        for entry in match_data:
            match_elo = entry["elo"]
            if not match_elo:
                continue
            if filter_party and entry.get("party_size") not in filter_party:
                continue
            won = 1 if entry.get("result") == 1 else 0

            def get_bucket(p):
                if elo_mode == "personal":
                    pe = int(p.get("player_elo", 0) or 0)
                    base = pe if pe > 0 else match_elo
                else:
                    base = match_elo
                return (base // step) * step

            for p in entry["teammates"]:
                if fc is not None:
                    c = (p.get("country") or "").lower()
                    if c not in fc:
                        continue
                b = get_bucket(p)
                tm_items[b].append((p, won))
                key = p.get("player_id") or p.get("nickname", "")
                if key in friends_set:
                    fr_items[b].append((p, won))
            for p in entry["enemies"]:
                if fc is not None:
                    c = (p.get("country") or "").lower()
                    if c not in fc:
                        continue
                b = get_bucket(p)
                en_items[b].append((p, won))
            if entry.get("my_stats"):
                me = entry["my_stats"]
                if fc is not None:
                    c = (me.get("country") or "").lower()
                    if c not in fc:
                        continue
                b = get_bucket(me)
                pl_items[b].append((me, won))

        def _s(vals):
            if not vals:
                return 0
            if median_mode:
                return round(statistics.median(vals), 2)
            return round(sum(vals) / len(vals), 2)

        def agg(items):
            if not items:
                return None
            players = [p for p, _ in items]
            wr_values = []
            for p, w in items:
                pw = p.get("player_winrate", 0)
                wr_values.append(float(pw) if pw else w * 100)

            kd_vals = [p.get("kd_ratio", 0) for p in players
                       if p.get("kd_ratio")]
            adr_vals = [p.get("adr", 0) for p in players if p.get("adr")]
            return {
                "count": len(players),
                "matches": len(items),
                "wr": round(_s(wr_values), 1),
                "kd": _s(kd_vals),
                "kr": _s([p.get("kr_ratio", 0) for p in players
                          if p.get("kr_ratio")]),
                "adr": _s(adr_vals),
                "hs": _s([p.get("headshots_percent", 0) for p in players
                          if p.get("headshots_percent")]),
                "kills": _s([p.get("kills", 0) for p in players]),
                "deaths": _s([p.get("deaths", 0) for p in players]),
                "assists": _s([p.get("assists", 0) for p in players]),
                "rating": _s([p.get("rating", 0) for p in players
                              if p.get("rating")]),
                "swing": _s([p.get("swing", 0) for p in players
                             if p.get("swing")]),
                # Доп. статистика для tooltip
                "kd_min": min(kd_vals) if kd_vals else 0,
                "kd_max": max(kd_vals) if kd_vals else 0,
                "adr_min": min(adr_vals) if adr_vals else 0,
                "adr_max": max(adr_vals) if adr_vals else 0,
            }

        tm = {b: agg(tm_items[b]) for b in tm_items}
        en = {b: agg(en_items[b]) for b in en_items}
        pl = {b: agg(pl_items[b]) for b in pl_items}
        fr = {b: agg(fr_items[b]) for b in fr_items}
        return tm, en, pl, fr

    def extract_countries(self, match_data):
        c = set()
        for entry in match_data:
            for p in entry["teammates"] + entry["enemies"]:
                cc = p.get("country", "")
                if cc:
                    c.add(cc.lower())
        return sorted(c)

    def collect_all_elos(self, match_data):
        elos = []
        for entry in match_data:
            for p in entry["teammates"] + entry["enemies"]:
                pe = int(p.get("player_elo", 0) or 0)
                if pe > 0:
                    elos.append(pe)
        return elos

    def build_deep_conclusions(self, match_data, friends_set):
        """Собирает данные для страницы выводов."""
        from collections import defaultdict
        import statistics as st

        # 1. Влияние друзей
        friends_data = defaultdict(lambda: {
            "with": [], "without": []})
        # 2. Влияние стран
        country_teammates = defaultdict(list)
        country_enemies = defaultdict(list)
        # 3. Влияние размера пати
        by_party = defaultdict(list)

        for entry in match_data:
            won = int(entry.get("result", 0) or 0)
            my_kd = float(entry.get("my_stats", {}).get("kd_ratio", 0) or 0)
            party = entry.get("party_size", 1)
            by_party[party].append(won)
            for p in entry["teammates"]:
                c = (p.get("country") or "?").lower()
                kd = float(p.get("kd_ratio", 0) or 0)
                country_teammates[c].append((kd, won))
            for p in entry["enemies"]:
                c = (p.get("country") or "?").lower()
                kd = float(p.get("kd_ratio", 0) or 0)
                country_enemies[c].append((kd, won))
            for p in entry["teammates"]:
                key = p.get("player_id") or p.get("nickname", "")
                if key in friends_set:
                    friends_data[key]["with"].append((won, my_kd))

        def safe_mean(vals):
            return round(st.mean(vals), 2) if vals else 0

        out = {
            "by_party": {
                str(k): {
                    "matches": len(v),
                    "winrate": round(sum(v) / len(v) * 100, 1) if v else 0,
                }
                for k, v in sorted(by_party.items())
            },
            "by_country_teammates": {
                c: {
                    "count": len(v),
                    "avg_kd": safe_mean([x[0] for x in v]),
                    "winrate": round(sum(x[1] for x in v) / len(v) * 100, 1),
                }
                for c, v in sorted(country_teammates.items(),
                                    key=lambda x: -len(x[1]))[:15]
            },
            "by_country_enemies": {
                c: {
                    "count": len(v),
                    "avg_kd": safe_mean([x[0] for x in v]),
                    "loss_rate": round((1 - sum(x[1] for x in v) / len(v)) * 100, 1),
                }
                for c, v in sorted(country_enemies.items(),
                                    key=lambda x: -len(x[1]))[:15]
            },
            "friends_impact": {
                k: {
                    "matches": len(v["with"]),
                    "winrate": round(sum(x[0] for x in v["with"]) /
                                      max(len(v["with"]), 1) * 100, 1),
                    "my_kd": safe_mean([x[1] for x in v["with"]]),
                }
                for k, v in friends_data.items() if v["with"]
            },
        }
        return out
