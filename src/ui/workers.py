"""QThread воркеры."""
import asyncio
import logging
import traceback
import concurrent.futures
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("faceit_analytics")


class QuickWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str, str)
    finished = Signal(dict)
    error = Signal(str)
    cancelled = Signal()

    def __init__(self, steam_id, sources, player_service, csrep, parent=None):
        super().__init__(parent)
        self.steam_id = steam_id
        self.sources = sources
        self.player_service = player_service
        self.csrep = csrep
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._run())
            if self._stop:
                self.cancelled.emit()
                return
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")
        finally:
            loop.close()

    async def _run(self):
        data = {"steam_id": self.steam_id}
        sources = self.sources
        active = [k for k, v in sources.items() if v] or ["steam"]
        total = len(active)
        done = 0

        if sources.get("steam"):
            self.progress.emit(int(done / total * 100), "Steam...")
            self.log.emit("INFO", "→ Steam")
            try:
                s = await self.player_service.steam.fetch_player(
                    self.steam_id)
                if isinstance(s, dict):
                    data.update(s)
                    self.log.emit("INFO", f"  Steam: {s.get('nickname')} OK")
            except Exception as e:
                self.log.emit("WARN", f"  Steam: {e}")
            done += 1
            if self._stop:
                return data

        if sources.get("cswatch"):
            self.progress.emit(int(done / total * 100), "CSWatch...")
            self.log.emit("INFO", "→ CSWatch")
            try:
                c = await self.player_service.cswatch.fetch_player(
                    self.steam_id)
                if isinstance(c, dict):
                    data["cswatch_reputation"] = c.get("reputation_score", 0)
                    data["cswatch_risk"] = c.get("risk_level", "")
                    data["vac_banned"] = c.get("vac_banned", False)
                    data["game_banned"] = c.get("game_bans", 0) > 0
                    data["conviction_count"] = c.get("conviction_count", 0)
                    data["ai_severity"] = c.get("ai_severity")
                    data["last_ban_days"] = c.get("last_ban_days", 0)
                    self.log.emit("INFO",
                                  f"  CSWatch: risk={data['cswatch_risk']}")
            except Exception as e:
                self.log.emit("WARN", f"  CSWatch: {e}")
            done += 1
            if self._stop:
                return data

        if sources.get("faceit"):
            self.progress.emit(int(done / total * 100), "FACEIT...")
            self.log.emit("INFO", "→ FACEIT")
            try:
                f = await self.player_service.faceit.fetch_player(
                    self.steam_id)
                if isinstance(f, dict):
                    for k, v in f.items():
                        if v not in ("", 0, None, False, []):
                            data[k] = v
                    self.log.emit("INFO",
                                  f"  FACEIT: level={f.get('faceit_level')}, "
                                  f"elo={f.get('faceit_elo')}")
            except Exception as e:
                self.log.emit("WARN", f"  FACEIT: {e}")
            done += 1
            if self._stop:
                return data

        if sources.get("csstats"):
            self.progress.emit(int(done / total * 100), "CSStats...")
            self.log.emit("INFO", "→ CSStats")
            try:
                cs = await self.player_service.csstats.fetch_player(
                    self.steam_id)
                if isinstance(cs, dict):
                    data["csstats"] = cs
            except Exception as e:
                self.log.emit("WARN", f"  CSStats: {e}")
            done += 1
            if self._stop:
                return data

        self.progress.emit(int(done / total * 100), "CSRep...")
        self.log.emit("INFO", "→ CSRep")
        try:
            cr = self.csrep.fetch_player(self.steam_id)
            if isinstance(cr, dict):
                for k, v in cr.items():
                    if k not in ("steam_id", "source") and v:
                        data[k] = v
                self.log.emit("INFO",
                              f"  CSRep: trust={cr.get('trust_score')}")
        except Exception as e:
            self.log.emit("WARN", f"  CSRep: {e}")

        self.progress.emit(100, "Готово")
        return data


class DeepWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str, str)
    finished = Signal(dict)
    error = Signal(str)
    cancelled = Signal()

    def __init__(self, steam_id, mode, player_service,
                 match_aggregator, db, parent=None):
        super().__init__(parent)
        self.steam_id = steam_id
        self.mode = mode
        self.player_service = player_service
        self.agg = match_aggregator
        self.db = db
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._run())
            if self._stop:
                self.cancelled.emit()
                return
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")
        finally:
            loop.close()

    async def _run(self):
        result = {"match_data": [], "teammates": {}, "enemies": {},
                  "player": {}, "friends": {}, "countries": [],
                  "matches": [], "all_elos": [], "conclusions": {}}

        self.progress.emit(5, "Загрузка 100 матчей...")
        self.log.emit("INFO", "→ FACEIT matches")
        matches = await self.player_service.fetch_matches(self.steam_id,
                                                          limit=100)
        if not matches:
            raise RuntimeError("Матчи не найдены")
        self.log.emit("INFO", f"  ✅ {len(matches)} матчей")
        result["matches"] = matches
        if self._stop:
            return result

        self.progress.emit(15, "Анализ...")
        from src.core.analytics.deep import DeepAnalyzer
        player = self.db.get_player(self.steam_id) or {}
        deep_result = DeepAnalyzer().analyze(player.get("data", {}), matches)
        result["deep_result"] = deep_result
        if self._stop:
            return result

        my_player_id = ""
        if isinstance(player.get("data"), dict):
            my_player_id = player["data"].get("faceit_id", "")
        if not my_player_id:
            f = await self.player_service.faceit.fetch_player(self.steam_id)
            if isinstance(f, dict):
                my_player_id = f.get("faceit_id", "")
        self.log.emit("INFO", f"  Player ID: {my_player_id[:8]}...")

        # Полная загрузка всегда
        limit = 30
        self.progress.emit(20, "Сбор тиммейтов/врагов...")

        def progress_cb(cur, total, msg):
            pct = 20 + int(cur / total * 60)
            self.progress.emit(pct, f"{cur}/{total}")
            if cur % 5 == 0 or cur == total:
                self.log.emit("INFO", f"  [{cur}/{total}]")

        self.agg.on_progress = progress_cb
        match_data = await self.agg.collect_matches(
            matches, my_player_id, limit=limit,
            enrich_countries=True, enrich_elo=True)
        result["match_data"] = match_data
        if not match_data:
            return result
        if self._stop:
            return result
        self.log.emit("INFO", f"  ✅ {len(match_data)} матчей")

        self.progress.emit(85, "Агрегация...")
        friends_set = self.agg.detect_friends(match_data, min_appearances=2)
        tm, en, pl, fr = self.agg.build_stats_by_elo(
            match_data, elo_step=50, friends_set=friends_set)
        countries = self.agg.extract_countries(match_data)
        all_elos = self.agg.collect_all_elos(match_data)
        conclusions = self.agg.build_deep_conclusions(match_data,
                                                       friends_set)
        result["teammates"] = tm
        result["enemies"] = en
        result["player"] = pl
        result["friends"] = fr
        result["countries"] = countries
        result["all_elos"] = all_elos
        result["friends_set"] = friends_set
        result["conclusions"] = conclusions

        if all_elos:
            self.log.emit("INFO",
                          f"  ELO range: {min(all_elos)}-{max(all_elos)}")
        self.progress.emit(100, "Готово")
        return result
