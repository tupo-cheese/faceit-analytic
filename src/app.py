"""Точка входа."""
import sys
import logging
import traceback
import re
import time
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout,
    QTextEdit, QPushButton)

from src.ui.main_window import MainWindow
from src.ui.theme import DARK_QSS
from src.core.database import Database
from src.core.cache_manager import CacheManager
from src.services.player_service import PlayerService
from src.services.auth_service import AuthService
from src.services.link_parser import LinkParser
from src.services.match_aggregator import MatchAggregator
from src.data_sources.csrep import CSRepSource
from src.ui.workers import QuickWorker, DeepWorker
from src.ui.debug_console import get_log_handler, audit_ui, audit_modules

logger = logging.getLogger("faceit_analytics")
DATA_TTL = 3600


class App:
    def __init__(self):
        self.qapp = QApplication(sys.argv)
        self.qapp.setStyleSheet(DARK_QSS)
        self.current_steam_id = None
        self._player_cache = {}
        self._deep_cache = {}
        self._friends_set = set()
        self._quick_worker = None
        self._deep_worker = None
        self._setup_logging()
        self.db = Database()
        self.cache = CacheManager()
        self.auth = AuthService()
        self.player_service = PlayerService(self.db, self.cache)
        self.csrep = CSRepSource(self.cache)
        self.aggregator = MatchAggregator(self.cache, self.db, elo_step=50)
        self.window = MainWindow()
        self._wire()
        logger.info("Приложение запущено")

    def _setup_logging(self):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        for h in list(root.handlers):
            root.removeHandler(h)
        ui_handler = get_log_handler()
        ui_handler.setLevel(logging.DEBUG)
        root.addHandler(ui_handler)
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(logging.INFO)
        root.addHandler(stream)

    def _wire(self):
        self.window.search_input.returnPressed.connect(self._on_search)
        self.window.nav_buttons["quick"].clicked.connect(self._on_quick_click)
        self.window.nav_buttons["deep"].clicked.connect(self._on_deep_click)
        self.window.nav_buttons["matches"].clicked.connect(self._on_matches_click)
        self.window.command_input.returnPressed.connect(self._on_command)
        self.window.btn_cancel.clicked.connect(self._on_cancel)
        self.window.deep_page.comparison.filters_changed.connect(
            self._on_filters_changed)

    def _on_cancel(self):
        if self._quick_worker and self._quick_worker.isRunning():
            self._quick_worker.stop()
        if self._deep_worker and self._deep_worker.isRunning():
            self._deep_worker.stop()

    def _on_filters_changed(self, filters):
        dp = self.window.deep_page
        if not dp._aggregator or not dp._match_data:
            return
        step = filters.get("elo_step", 50)
        party = filters.get("party_sizes")
        countries = filters.get("countries")
        median_mode = filters.get("median_mode", False)
        elo_mode = filters.get("elo_mode", "personal")
        logger.info(f"filters: mode={elo_mode}, step={step}")
        tm, en, pl, fr = dp._aggregator.build_stats_by_elo(
            dp._match_data, elo_step=step, filter_party=party,
            friends_set=self._friends_set, filter_countries=countries,
            median_mode=median_mode, elo_mode=elo_mode)
        dp.comparison.set_full_data(pl, tm, en, fr)
        dp._update_elo_table(tm, en, pl, step)

    def _is_fresh(self, cache, key):
        return key in cache and (time.time() - cache[key][0]) < DATA_TTL

    def _audit_all(self):
        logger.info("══════════ FULL AUDIT ══════════")
        dp = self.window.deep_page
        logger.info(f"_match_data: {len(dp._match_data)}")
        logger.info(f"Chart player: {len(dp.comparison._player_data)}")
        logger.info(f"Chart teammates: {len(dp.comparison._teammates_data)}")
        logger.info(f"Chart enemies: {len(dp.comparison._enemies_data)}")
        if dp.comparison._player_data:
            for b, d in sorted(dp.comparison._player_data.items()):
                logger.info(f"  Player {b}: n={d.get('count')}")
        if dp.comparison._teammates_data:
            for b, d in sorted(dp.comparison._teammates_data.items())[:5]:
                logger.info(f"  Teammate {b}: n={d.get('count')}")
        # ELO резолвер
        from src.services.player_elo_resolver import get_elo_resolver
        r = get_elo_resolver()
        logger.info(f"ELO cache: {len(r._cache)}")
        ok = sum(1 for v in r._cache.values() if v.get("elo"))
        logger.info(f"  с ELO: {ok}")
        # Реальные ELO из match_data
        if dp._match_data:
            elos = []
            for entry in dp._match_data:
                for p in entry["teammates"] + entry["enemies"]:
                    e = p.get("player_elo", 0)
                    if e:
                        elos.append(e)
            if elos:
                logger.info(f"ELO range: {min(elos)}-{max(elos)} "
                            f"({len(elos)} значений)")
            else:
                logger.warning("player_elo = 0 у всех игроков!")

    def _dump_elo(self, args):
        """Диагностика ELO резолвера."""
        parts = args.split() if args else []
        nick = parts[0] if parts else "APMATYPA-"
        pid = parts[1] if len(parts) > 1 else ""
        from src.services.player_elo_resolver import get_elo_resolver
        r = get_elo_resolver()
        r.dump_one(nickname=nick, player_id=pid)

    def _on_search(self):
        text = self.window.search_input.text().strip()
        if not text:
            return
        try:
            parsed = LinkParser.detect(text)
            steam_id = None
            if parsed["platform"] == "steam_id":
                steam_id = parsed["value"]
            elif parsed["platform"] == "steam_vanity":
                self.window.set_status("Разрешаем vanity URL...")
                steam_id = self._resolve_vanity(parsed["value"])
            elif parsed["platform"] in ("faceit_nick", "nickname"):
                res = self.db.search_players(parsed["value"])
                steam_id = res[0]["steam_id"] if res else None
            if not steam_id:
                self.window.set_status("❌ Не распознано")
                return
            self.current_steam_id = steam_id
            self.window.mark_url_loaded()
            self._start_quick_load(steam_id)
        except Exception as e:
            logger.error(f"Ошибка: {e}\n{traceback.format_exc()}")

    def _resolve_vanity(self, vanity):
        import urllib.request
        try:
            req = urllib.request.Request(
                f"https://steamcommunity.com/id/{vanity}/?xml=1",
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r"<steamID64>(\d+)</steamID64>", xml)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def _start_quick_load(self, steam_id):
        if self._quick_worker and self._quick_worker.isRunning():
            return
        self.window.set_loading(True, "Загрузка профиля...")
        sources = self.window.get_sources()
        self._quick_worker = QuickWorker(
            steam_id, sources, self.player_service, self.csrep)
        self._quick_worker.progress.connect(self.window.set_progress)
        self._quick_worker.log.connect(self._worker_log)
        self._quick_worker.finished.connect(self._on_quick_finished)
        self._quick_worker.error.connect(self._on_worker_error)
        self._quick_worker.start()

    def _worker_log(self, level, msg):
        getattr(logger, level.lower(), logger.info)(msg)

    def _on_quick_finished(self, data):
        self.window.set_loading(False)
        steam_id = data.get("steam_id")
        if steam_id:
            self._player_cache[steam_id] = (time.time(), data)
        self.window.quick_page.card.set_data(data)
        self.window.quick_page.set_quick_stats(data)
        self.window.set_status(f"✅ {data.get('nickname', '?')}")
        try:
            self.db.upsert_player(steam_id, data,
                faceit_id=data.get("faceit_id", ""),
                nickname=data.get("nickname", ""),
                avatar=data.get("avatar_url", ""), source="multi")
        except Exception:
            pass

    def _on_worker_error(self, msg):
        self.window.set_loading(False)
        logger.error(msg)
        self.window.set_status("❌ Ошибка (см. консоль)")

    def _on_quick_click(self):
        if not self.current_steam_id:
            t = self.window.search_input.text().strip()
            if t:
                self._on_search()
            return
        self.window._has_url = True
        self.window.stack.setCurrentWidget(self.window.quick_page)
        self.window.nav_buttons["quick"].setChecked(True)
        if not self._is_fresh(self._player_cache, self.current_steam_id):
            self._start_quick_load(self.current_steam_id)
        else:
            d = self._player_cache[self.current_steam_id][1]
            self.window.quick_page.card.set_data(d)
            self.window.quick_page.set_quick_stats(d)

    def _on_deep_click(self):
        if not self.current_steam_id:
            t = self.window.search_input.text().strip()
            if t:
                self._on_search()
            return
        self.window._has_url = True
        self.window.stack.setCurrentWidget(self.window.deep_page)
        self.window.nav_buttons["deep"].setChecked(True)
        if not self._is_fresh(self._deep_cache, self.current_steam_id):
            self._start_deep_load()
        else:
            c = self._deep_cache[self.current_steam_id]
            self.window.deep_page.set_deep_analysis(c[1])
            self.window.matches_page.set_matches(c[2])

    def _on_matches_click(self):
        if not self.current_steam_id:
            t = self.window.search_input.text().strip()
            if t:
                self._on_search()
            return
        self.window._has_url = True
        self.window.stack.setCurrentWidget(self.window.matches_page)
        self.window.nav_buttons["matches"].setChecked(True)
        if not self._is_fresh(self._deep_cache, self.current_steam_id):
            self._start_deep_load()

    def _start_deep_load(self):
        if self._deep_worker and self._deep_worker.isRunning():
            return
        logger.info("Запуск deep")
        self.window.set_loading(True, "Глубокая аналитика...")
        self._deep_worker = DeepWorker(
            self.current_steam_id, "full", self.player_service,
            self.aggregator, self.db)
        self._deep_worker.progress.connect(self.window.set_progress)
        self._deep_worker.log.connect(self._worker_log)
        self._deep_worker.finished.connect(self._on_deep_finished)
        self._deep_worker.error.connect(self._on_worker_error)
        self._deep_worker.start()

    def _on_deep_finished(self, result):
        self.window.set_loading(False)
        try:
            deep_result = result.get("deep_result", {})
            matches = result.get("matches", [])
            match_data = result.get("match_data", [])
            self.window.deep_page.set_deep_analysis(deep_result)
            self.window.matches_page.set_matches(matches)
            dp = self.window.deep_page
            dp.set_match_data(match_data)
            dp.set_aggregator(self.aggregator)
            dp.comparison.set_countries(result.get("countries", []))
            dp.comparison.set_full_data(
                result.get("player", {}),
                result.get("teammates", {}),
                result.get("enemies", {}),
                result.get("friends", {}))
            dp._update_elo_table(
                result.get("teammates", {}),
                result.get("enemies", {}),
                result.get("player", {}), 50)
            dp.set_conclusions(result.get("conclusions", {}))
            self._friends_set = result.get("friends_set", set())
            self._deep_cache[self.current_steam_id] = (
                time.time(), deep_result, matches)
            self._update_quick_from_matches(matches)
            elos = result.get("all_elos", [])
            if elos:
                logger.info(f"✅ ELO range: {min(elos)}-{max(elos)}")
        except Exception as e:
            logger.error(f"Render error: {e}\n{traceback.format_exc()}")

    def _update_quick_from_matches(self, matches):
        if not matches:
            return
        total = len(matches)
        wins = sum(1 for m in matches if int(m.get("result", 0) or 0) == 1)
        kills = sum(int(m.get("kills", 0) or 0) for m in matches)
        deaths = sum(int(m.get("deaths", 0) or 0) for m in matches)
        adr = [float(m.get("adr", 0) or 0) for m in matches if m.get("adr")]
        hs = [float(m.get("headshots_percent", 0) or 0) for m in matches
              if m.get("headshots_percent")]
        avg_kd = round(kills / max(deaths, 1), 2)
        win_rate = round(wins / total * 100, 1) if total else 0
        data = self._player_cache.get(self.current_steam_id, (0, {}))[1]
        if not isinstance(data, dict):
            data = {}
        data.update({
            "matches_total": total,
            "win_rate": f"{win_rate}%",
            "avg_kd": avg_kd,
            "kd": avg_kd,
            "adr": round(sum(adr) / len(adr), 1) if adr else 0,
            "avg_hs": f"{round(sum(hs) / len(hs), 1) if hs else 0}%",
        })
        self._player_cache[self.current_steam_id] = (time.time(), data)
        self.window.quick_page.set_quick_stats(data)

    def _on_command(self):
        raw = self.window.command_input.text().strip()
        if not raw:
            return
        self.window.command_input.clear()
        for s in re.split(r"[;\n]+", raw):
            s = s.strip()
            if not s:
                continue
            logger.info(f"[CMD] {s}")
            try:
                self._execute_command(s)
            except Exception as e:
                logger.error(f"Ошибка: {e}\n{traceback.format_exc()}")

    def _execute_command(self, cmd):
        parts = cmd.split(maxsplit=1)
        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if name == "help":
            self.window.show_commands_dialog()
        elif name == "clear":
            self.window.log_view.clear()
        elif name == "clear_cache":
            self.cache.clear()
            logger.info("Кэш очищен")
        elif name == "audit_all":
            self._audit_all()
        elif name == "dump_elo":
            self._dump_elo(args)
        elif name == "deep":
            if args:
                self.current_steam_id = args.strip()
                self.window.mark_url_loaded()
            self._start_deep_load()
        elif name == "quick":
            if args:
                self.current_steam_id = args.strip()
                self.window.mark_url_loaded()
            if self.current_steam_id:
                self._start_quick_load(self.current_steam_id)
        elif name == "elo_cache":
            from src.services.player_elo_resolver import get_elo_resolver
            r = get_elo_resolver()
            logger.info(f"ELO cache: {len(r._cache)}")
            ok = sum(1 for v in r._cache.values() if v.get("elo"))
            logger.info(f"  с ELO: {ok}")
            for k, v in list(r._cache.items())[:10]:
                logger.info(f"  {k[:16]}: elo={v.get('elo')}")
        else:
            logger.warning(f"Неизвестно: {name}")

    def run(self):
        self.window.show()
        return self.qapp.exec()


def main():
    try:
        app = App()
        sys.exit(app.run())
    except Exception as e:
        tb = traceback.format_exc()
        qapp = QApplication.instance() or QApplication(sys.argv)
        dlg = QDialog()
        dlg.setWindowTitle("Ошибка")
        dlg.resize(900, 500)
        layout = QVBoxLayout(dlg)
        edit = QTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(f"{e}\n\n{tb}")
        layout.addWidget(edit)
        btn = QPushButton("Закрыть")
        btn.clicked.connect(dlg.reject)
        layout.addWidget(btn)
        dlg.exec()
        sys.exit(1)


if __name__ == "__main__":
    main()
