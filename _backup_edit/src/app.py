import sys
import logging
import traceback
import re
import time
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
from src.ui.debug_console import get_log_handler

logger = logging.getLogger('faceit_analytics')
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
        self._deep_match_limit = 30
        self._setup_logging()
        self.db = Database()
        self.cache = CacheManager()
        self.auth = AuthService()
        self.player_service = PlayerService(self.db, self.cache)
        from src.core.player_store import get_player_store
        self.player_store = get_player_store()
        self.csrep = CSRepSource(self.cache)
        self.aggregator = MatchAggregator(self.cache, self.db, elo_step=50)
        self.window = MainWindow()
        self._wire()
        self._restore_from_store()
        logger.info('Приложение запущено')

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
        self.window.nav_group.buttonClicked.connect(self._on_nav_button)
        self.window.btn_quick.refresh_clicked.connect(self._refresh_quick)
        self.window.btn_deep.refresh_clicked.connect(self._refresh_deep)
        self.window.load_more_clicked.connect(self._on_load_more_gui)
        self.window.command_input.returnPressed.connect(self._on_command)
        self.window.btn_cancel.clicked.connect(self._on_cancel)
        self.window.deep_page.comparison.filters_changed.connect(
            self._on_filters_changed)
        if hasattr(self.window, 'players_combo'):
            self.window.players_combo.currentIndexChanged.connect(
                self._on_player_combo_changed)
        if hasattr(self.window.deep_page, 'reload_requested'):
            self.window.deep_page.reload_requested.connect(self._on_reload_deep)
            self.window.deep_page.load_more_requested.connect(
                self._on_load_more_clicked)

    def _restore_from_store(self):
        try:
            from src.core.persistence import get_deep_cache
            dc = get_deep_cache()
            saved = dc.list_saved()
            logger.info(f'Persisted deep: {len(saved)} игроков на диске')
            self.window.refresh_players_combo(
                self.player_store.list_sorted(), '')
        except Exception as e:
            logger.warning(f'restore err: {e}')

    def _on_cancel(self):
        if self._quick_worker and self._quick_worker.isRunning():
            self._quick_worker.stop()
        if self._deep_worker and self._deep_worker.isRunning():
            self._deep_worker.stop()

    def _on_filters_changed(self, filters):
        dp = self.window.deep_page
        if not dp._aggregator or not dp._match_data:
            return
        step = filters.get('elo_step', 50)
        party = filters.get('party_sizes')
        countries = filters.get('countries')
        median_mode = filters.get('median_mode', False)
        elo_mode = filters.get('elo_mode', 'personal')
        tm, en, pl, fr = dp._aggregator.build_stats_by_elo(
            dp._match_data, elo_step=step, filter_party=party,
            friends_set=self._friends_set, filter_countries=countries,
            median_mode=median_mode, elo_mode=elo_mode)
        dp.comparison.set_full_data(pl, tm, en, fr)
        dp._update_elo_table(tm, en, pl, step)

    def _is_fresh(self, cache, key):
        return key in cache and time.time() - cache[key][0] < DATA_TTL

    # ─────────────── НАВИГАЦИЯ (без запросов) ───────────────
    def _on_nav_button(self, btn):
        idx = self.window.nav_group.id(btn)
        if idx == 0:
            self._show_quick()
        elif idx == 1:
            self._show_deep()
        elif idx == 2:
            self._show_matches()

    def _show_quick(self):
        self.window._has_url = True
        self.window.stack.setCurrentWidget(self.window.quick_page)
        if not self.current_steam_id:
            self.window.set_status('👋 Введи URL игрока и нажми Enter')
            return
        cached = self._player_cache.get(self.current_steam_id)
        if cached:
            d = cached[1]
            self.window.quick_page.card.set_data(d)
            self.window.quick_page.set_quick_stats(d)
            self.window.set_status('⚡ Quick из памяти (↻ — обновить)')
        else:
            self.window.set_status('нет quick — нажми ↻ для загрузки')

    def _show_deep(self):
        self.window._has_url = True
        self.window.stack.setCurrentWidget(self.window.deep_page)
        if not self.current_steam_id:
            self.window.set_status('👋 Введи URL игрока')
            return
        c = self._deep_cache.get(self.current_steam_id)
        if c:
            self._render_deep_from_cache(c[1], c[2])
            self.window.set_status('🔬 Deep из памяти (↻ — обновить)')
            return
        try:
            from src.core.persistence import get_deep_cache
            data = get_deep_cache().load(self.current_steam_id)
            if data and data.get('result'):
                self._deep_cache[self.current_steam_id] = (
                    time.time(), data['result'], data.get('matches', []))
                self._render_deep_from_cache(data['result'],
                                              data.get('matches', []))
                self.window.set_status('📂 Deep из диска (↻ — пересчитать)')
                return
        except Exception as e:
            logger.warning(f'load persisted err: {e}')
        self.window.set_status('нет deep — нажми ↻ или 🔬 Пересчитать')

    def _show_matches(self):
        self.window._has_url = True
        self.window.stack.setCurrentWidget(self.window.matches_page)
        if not self.current_steam_id:
            return
        c = self._deep_cache.get(self.current_steam_id)
        if c:
            self.window.matches_page.set_matches(c[2], c[1].get('match_data', []))
        else:
            try:
                from src.core.persistence import get_deep_cache
                data = get_deep_cache().load(self.current_steam_id)
                if data:
                    self.window.matches_page.set_matches(
                        data.get('matches', []),
                        data.get('result', {}).get('match_data', []))
            except Exception:
                pass

    # ─────────────── РЕФРЕШ (загрузка) ───────────────
    def _refresh_quick(self):
        if not self.current_steam_id:
            self.window.set_status('Сначала введи URL игрока')
            return
        logger.info('↻ refresh quick')
        self._player_cache.pop(self.current_steam_id, None)
        self.cache.clear_namespace('steam_player')
        self.cache.clear_namespace('faceit_player')
        self.cache.clear_namespace('cswatch')
        self.cache.clear_namespace('csstats_player')
        self._start_quick_load(self.current_steam_id)

    def _refresh_deep(self):
        if not self.current_steam_id:
            self.window.set_status('Сначала введи URL игрока')
            return
        logger.info('↻ refresh deep')
        self._deep_cache.pop(self.current_steam_id, None)
        try:
            from src.core.persistence import get_deep_cache
            get_deep_cache().delete(self.current_steam_id)
        except Exception:
            pass
        self._start_deep_load()

    # ─────────────── Поиск ───────────────
    def _on_search(self):
        text = self.window.search_input.text().strip()
        if not text:
            return
        try:
            parsed = LinkParser.detect(text)
            steam_id = None
            if parsed['platform'] == 'steam_id':
                steam_id = parsed['value']
            elif parsed['platform'] == 'steam_vanity':
                self.window.set_status('Разрешаем vanity URL...')
                steam_id = self._resolve_vanity(parsed['value'])
            elif parsed['platform'] in ('faceit_nick', 'nickname'):
                res = self.db.search_players(parsed['value'])
                steam_id = res[0]['steam_id'] if res else None
                if not steam_id:
                    steam_id = self.player_store.find(parsed['value'])
            if not steam_id:
                self.window.set_status('❌ Не распознано')
                return
            self.current_steam_id = steam_id
            self.window.mark_url_loaded()
            self._start_quick_load(steam_id)
        except Exception as e:
            logger.error(f'Ошибка: {e}\n{traceback.format_exc()}')

    def _resolve_vanity(self, vanity):
        import urllib.request
        try:
            req = urllib.request.Request(
                f'https://steamcommunity.com/id/{vanity}/?xml=1',
                headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml = resp.read().decode('utf-8', errors='ignore')
            m = re.search(r'<steamID64>(\d+)</steamID64>', xml)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def _start_quick_load(self, steam_id):
        if self._quick_worker and self._quick_worker.isRunning():
            return
        self.window.set_loading(True, 'Загрузка профиля...')
        sources = self.window.get_sources()
        self._quick_worker = QuickWorker(steam_id, sources,
                                          self.player_service, self.csrep)
        self._quick_worker.progress.connect(self.window.set_progress)
        self._quick_worker.log.connect(self._worker_log)
        self._quick_worker.finished.connect(self._on_quick_finished)
        self._quick_worker.error.connect(self._on_worker_error)
        self._quick_worker.start()

    def _worker_log(self, level, msg):
        getattr(logger, level.lower(), logger.info)(msg)

    def _on_quick_finished(self, data):
        self.window.set_loading(False)
        steam_id = data.get('steam_id')
        if steam_id:
            self._player_cache[steam_id] = (time.time(), data)
        self.window.quick_page.card.set_data(data)
        self.window.quick_page.set_quick_stats(data)
        self.window.set_status(f"✅ {data.get('nickname', '?')}")
        try:
            self.db.upsert_player(steam_id, data,
                                   faceit_id=data.get('faceit_id', ''),
                                   nickname=data.get('nickname', ''),
                                   avatar=data.get('avatar_url', ''),
                                   source='multi')
        except Exception:
            pass
        try:
            self.player_store.upsert(steam_id,
                                     nickname=data.get('nickname', ''),
                                     faceit_id=data.get('faceit_id', ''),
                                     faceit_elo=data.get('faceit_elo', 0),
                                     faceit_level=data.get('faceit_level', 0),
                                     avatar_url=data.get('avatar_url', ''),
                                     country=data.get('country', ''))
            self.window.refresh_players_combo(
                self.player_store.list_sorted(), self.current_steam_id)
        except Exception as e:
            logger.warning(f'store err: {e}')

    def _on_worker_error(self, msg):
        self.window.set_loading(False)
        logger.error(msg)
        self.window.set_status('❌ Ошибка (см. консоль)')

    def _start_deep_load(self):
        if self._deep_worker and self._deep_worker.isRunning():
            logger.info('deep: воркер уже работает')
            return
        logger.info(f'Запуск deep (limit={self._deep_match_limit})')
        self.window.set_loading(True, 'Глубокая аналитика...')
        self._deep_worker = DeepWorker(
            self.current_steam_id, 'full',
            self.player_service, self.aggregator, self.db,
            match_limit=self._deep_match_limit)
        self._deep_worker.progress.connect(self.window.set_progress)
        self._deep_worker.log.connect(self._worker_log)
        self._deep_worker.finished.connect(self._on_deep_finished)
        self._deep_worker.error.connect(self._on_worker_error)
        if hasattr(self._deep_worker, 'partial'):
            self._deep_worker.partial.connect(self._on_deep_partial)
        self._deep_worker.start()

    def _on_deep_partial(self, data):
        """Стриминг: каждые 5 собранных матчей обновляем график."""
        try:
            md = data.get('match_data', [])
            n = data.get('count', len(md))
            if not md:
                return
            agg = self.aggregator
            if not agg:
                return
            friends_set = agg.detect_friends(md, min_appearances=2)
            tm, en, pl, fr = agg.build_stats_by_elo(
                md, elo_step=self._deep_match_limit or 50,
                friends_set=friends_set)
            dp = self.window.deep_page
            dp.set_match_data(md)
            dp.comparison.set_full_data(pl, tm, en, fr)
            self.window.set_status(f'🔬 Стриминг: {n} матчей собрано…')
        except Exception as e:
            logger.debug(f'partial err: {e}')

    def _on_deep_finished(self, result):
        self.window.set_loading(False)
        try:
            deep_result = result.get('deep_result', {})
            matches = result.get('matches', [])
            match_data = result.get('match_data', [])

            full_result = {
                'deep_result': deep_result,
                'teammates': result.get('teammates', {}),
                'enemies': result.get('enemies', {}),
                'player': result.get('player', {}),
                'friends': result.get('friends', {}),
                'countries': result.get('countries', []),
                'all_elos': result.get('all_elos', []),
                'conclusions': result.get('conclusions', {}),
                'match_data': match_data,
                'match_limit': result.get('match_limit', 30),
            }
            self._deep_cache[self.current_steam_id] = (
                time.time(), full_result, matches)

            try:
                from src.core.persistence import get_deep_cache
                get_deep_cache().save(self.current_steam_id, full_result,
                                       matches,
                                       elo_limit=self._deep_match_limit)
            except Exception as e:
                logger.warning(f'persist err: {e}')

            try:
                self.player_store.mark_deep(self.current_steam_id,
                                             len(matches))
                self.window.refresh_players_combo(
                    self.player_store.list_sorted(), self.current_steam_id)
            except Exception as e:
                logger.warning(f'store mark err: {e}')

            self._render_deep_from_cache(full_result, matches)
            self._update_quick_from_matches(matches)
        except Exception as e:
            logger.error(f'Render error: {e}\n{traceback.format_exc()}')

    def _render_deep_from_cache(self, full_result, matches):
        dp = self.window.deep_page
        dr = full_result.get('deep_result', {})
        dp.set_deep_analysis(dr)
        self.window.matches_page.set_matches(
            matches, full_result.get('match_data', []))
        if self.aggregator:
            dp.set_aggregator(self.aggregator)
        dp.set_match_data(full_result.get('match_data', []))
        self._friends_set = {k for k in
                              (full_result.get('friends', {}) or {})
                              if k != '__baseline__'}
        dp.comparison.set_countries(full_result.get('countries', []))
        dp.comparison.set_full_data(
            full_result.get('player', {}),
            full_result.get('teammates', {}),
            full_result.get('enemies', {}),
            full_result.get('friends', {}),
        )
        concl = full_result.get('conclusions', {})
        if concl:
            try:
                dp.set_conclusions(concl)
            except Exception as e:
                logger.warning(f'set_conclusions err: {e}')

    def _update_quick_from_matches(self, matches):
        if not matches:
            return
        total = len(matches)
        wins = sum(1 for m in matches if int(m.get('result', 0) or 0) == 1)
        kills = sum(int(m.get('kills', 0) or 0) for m in matches)
        deaths = sum(int(m.get('deaths', 0) or 0) for m in matches)
        adr = [float(m.get('adr', 0) or 0) for m in matches if m.get('adr')]
        hs = [float(m.get('headshots_percent', 0) or 0) for m in matches
              if m.get('headshots_percent')]
        avg_kd = round(kills / max(deaths, 1), 2)
        win_rate = round(wins / total * 100, 1) if total else 0
        data = self._player_cache.get(self.current_steam_id, (0, {}))[1]
        if not isinstance(data, dict):
            data = {}
        data.update({
            'matches_total': total,
            'win_rate': f'{win_rate}%',
            'avg_kd': avg_kd, 'kd': avg_kd,
            'adr': round(sum(adr) / len(adr), 1) if adr else 0,
            'avg_hs': f'{(round(sum(hs) / len(hs), 1) if hs else 0)}%',
        })
        self._player_cache[self.current_steam_id] = (time.time(), data)
        self.window.quick_page.set_quick_stats(data)

    def _on_load_more_gui(self, amount):
        pages = max(1, (amount + 99) // 100)
        logger.info(f'GUI: загрузить ещё {amount} матчей')
        self._cmd_load_more(str(pages))

    def _on_load_more_clicked(self, pages):
        self._cmd_load_more(str(pages))

    def _on_reload_deep(self, limit):
        logger.info(f'Пересчёт deep (limit={limit})')
        self._deep_match_limit = limit
        self._deep_cache.pop(self.current_steam_id, None)
        try:
            from src.core.persistence import get_deep_cache
            get_deep_cache().delete(self.current_steam_id)
        except Exception:
            pass
        self._start_deep_load()

    def _on_player_combo_changed(self, idx):
        try:
            sid = self.window.players_combo.itemData(idx)
        except Exception:
            return
        if not sid or sid == self.current_steam_id:
            return
        self._switch_to_player(sid)

    def _switch_to_player(self, steam_id):
        logger.info(f'Переключение на {steam_id}')
        self.current_steam_id = steam_id
        self.window._has_url = True

        cached = self._player_cache.get(steam_id)
        if cached:
            d = cached[1]
            self.window.quick_page.card.set_data(d)
            self.window.quick_page.set_quick_stats(d)

        deep = self._deep_cache.get(steam_id)
        if not deep:
            try:
                from src.core.persistence import get_deep_cache
                data = get_deep_cache().load(steam_id)
                if data and data.get('result'):
                    self._deep_cache[steam_id] = (
                        time.time(), data['result'], data.get('matches', []))
                    deep = self._deep_cache[steam_id]
            except Exception:
                pass
        if deep:
            try:
                self._render_deep_from_cache(deep[1], deep[2])
            except Exception as e:
                logger.error(f'render cache err: {e}')

        self.window.stack.setCurrentWidget(self.window.quick_page)
        self.window.btn_quick.setChecked(True)
        self.window.set_status(f'✅ Переключено на {steam_id[:12]}')

    # ─────────────── Команды ───────────────
    def _on_command(self):
        raw = self.window.command_input.text().strip()
        if not raw:
            return
        self.window.command_input.clear()
        for s in re.split(r'[;\n]+', raw):
            s = s.strip()
            if not s:
                continue
            logger.info(f'[CMD] ▶ {s}')
            t0 = time.time()
            try:
                self._execute_command(s)
                logger.info(f'[CMD] ✓ {s} ({time.time() - t0:.2f}s)')
            except Exception as e:
                logger.error(f'[CMD] ✗ {s}: {e}\n{traceback.format_exc()}')

    def _execute_command(self, cmd):
        parts = cmd.split(maxsplit=1)
        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        if name == 'help': self.window.show_commands_dialog()
        elif name == 'clear': self.window.log_view.clear()
        elif name == 'clear_cache':
            self.cache.clear(); logger.info('Кэш очищен')
        elif name == 'clear_matches':
            self.cache.clear_namespace('faceit_matches')
            self.cache.clear_namespace('match_players')
            logger.info('Кэш матчей очищен')
        elif name == 'audit_all': self._audit_all()
        elif name == 'dump_elo':
            from src.services.debug_tools import elo_check
            elo_check(args)
        elif name == 'deep': self._cmd_deep(args)
        elif name == 'quick':
            if args:
                self.current_steam_id = args.strip()
                self.window.mark_url_loaded()
            if self.current_steam_id:
                self._start_quick_load(self.current_steam_id)
        elif name == 'elo_cache':
            from src.services.player_elo_resolver import get_elo_resolver
            r = get_elo_resolver()
            ok = sum(1 for v in r._cache.values() if v.get('elo'))
            logger.info(f'ELO cache: {len(r._cache)} записей, с ELO: {ok}')
        elif name == 'players': self._list_players()
        elif name == 'use': self._cmd_use(args)
        elif name == 'summary': self._cmd_summary(args)
        elif name == 'full_report': self._cmd_full_report(args)
        elif name == 'refresh': self._refresh_deep()
        elif name == 'load_more': self._cmd_load_more(args)
        elif name == 'match_stats': self._cmd_match_stats(args)
        elif name == 'set_limit':
            try:
                self._deep_match_limit = max(5, int(args.strip() or '30'))
                self.window.deep_page.set_limit(self._deep_match_limit)
                logger.info(f'deep limit = {self._deep_match_limit}')
            except Exception:
                logger.warning('set_limit <число>')
        elif name == 'countries': self._cmd_countries(args)
        elif name == 'health_check':
            from src.services.debug_tools import health_check
            health_check(self, args)
        elif name == 'probe_sources':
            from src.services.debug_tools import probe_sources
            probe_sources(self, args)
        elif name == 'report_coverage':
            from src.services.debug_tools import report_coverage
            report_coverage(self, args)
        elif name == 'debug_all':
            from src.services.debug_tools import run_full_debug
            run_full_debug(self, args)
        elif name == 'faceit_debug':
            from src.services.debug_tools import faceit_debug
            faceit_debug(self, args)
        elif name == 'elo_check':
            from src.services.debug_tools import elo_check
            elo_check(args)
        elif name == 'agg_check':
            from src.services.debug_tools import agg_check
            agg_check(self, args)
        elif name == 'proxy_status':
            from src.services.debug_tools import proxy_status
            proxy_status(args)
        elif name == 'proxy_reload':
            from src.services.debug_tools import proxy_reload
            proxy_reload(args)
        elif name == 'proxy_verify':
            from src.services.debug_tools import proxy_verify
            proxy_verify(args)
        elif name == 'check_match':
            from src.services.debug_tools import check_match
            check_match(self, args)
        elif name == 'bucket_players':
            from src.services.debug_tools import bucket_players
            bucket_players(self, args)
        elif name == 'deep_counts':
            from src.services.debug_tools import deep_counts
            deep_counts(self, args)
        elif name == 'retry_failed':
            from src.services.debug_tools import retry_failed
            retry_failed(self, args)
        elif name == 'proxy_stats':
            from src.services.debug_tools import proxy_stats
            proxy_stats(args)
        elif name == 'proxy_fetch':
            from src.services.proxy_fetcher import fetch_proxies
            n = fetch_proxies(limit_total=2000, append=True)
            from src.services.proxy_rotator import get_proxy_rotator
            pr = get_proxy_rotator()
            pr.reload()
            logger.info(f'proxy_fetch: +{n}, всего {pr.total}')
        elif name == 'deep_files':
            from src.core.persistence import get_deep_cache
            dc = get_deep_cache()
            for sid, at, mc in dc.list_saved():
                logger.info(f'  {sid[:20]}... {mc} матчей, '
                            f'{int(time.time()-at)}s назад')
        else:
            logger.warning(f'Неизвестно: {name}')

    def _cmd_deep(self, args):
        parts = args.split()
        sid = None
        limit = None
        for p in parts:
            if p.isdigit() and len(p) >= 17:
                sid = p
            elif p.isdigit():
                limit = int(p)
        if sid:
            self.current_steam_id = sid
            self.window.mark_url_loaded()
        if limit:
            self._deep_match_limit = limit
            self.window.deep_page.set_limit(limit)
        if not self.current_steam_id:
            logger.warning('deep: нет steam_id')
            return
        self._start_deep_load()

    def _cmd_load_more(self, args):
        try:
            pages = max(1, int(args.strip() or '1'))
        except Exception:
            pages = 1
        if not self.current_steam_id:
            logger.warning('load_more — нет активного игрока')
            return
        sid = self.current_steam_id
        target = pages * 100
        logger.info(f'Дозагрузка ~{target} матчей ({pages} страниц)')
        import asyncio as _a
        loop = _a.new_event_loop()
        t0 = time.time()
        try:
            for p in range(1, pages + 1):
                logger.info(f'  страница {p}/{pages}…')
                result = loop.run_until_complete(
                    self.player_service.faceit.fetch_matches_more(sid, page=p))
                logger.info(f'  page={p}: всего {len(result)} матчей')
        finally:
            loop.close()
        cached = self.cache.get('faceit_matches', sid) or []
        logger.info(f'Итого: {len(cached)} матчей за {time.time()-t0:.0f}s')
        try:
            self.window.deep_page.set_cache_count(len(cached))
        except Exception:
            pass
        logger.info(f'Совет: set_limit {len(cached)}; clear_matches; deep')

    def _cmd_match_stats(self, args):
        sid = self.current_steam_id
        if not sid:
            logger.warning('match_stats — нет игрока')
            return
        cached = self.cache.get('faceit_matches', sid) or []
        logger.info(f'Матчей в кэше: {len(cached)}')
        logger.info(f'deep limit: {self._deep_match_limit}')
        try:
            self.window.deep_page.set_cache_count(len(cached))
        except Exception:
            pass
        players_cached = 0
        for m in cached[:500]:
            mid = m.get('match_id') or m.get('id')
            if mid and self.cache.get('match_players', mid):
                players_cached += 1
        logger.info(f'Деталей в кэше: {players_cached}')

    def _list_players(self):
        items = self.player_store.list_sorted()
        logger.info(f'Загружено игроков: {len(items)}')
        for i, (sid, rec) in enumerate(items[:30], 1):
            nick = rec.get('nickname', '?')
            elo = rec.get('faceit_elo', '?')
            deep = '🔬' if rec.get('has_deep') else '⚡'
            logger.info(f'  [{i}] {deep} {nick:20} ELO {elo:>5}  {sid[:16]}')
        self.window.refresh_players_combo(items, self.current_steam_id)

    def _cmd_use(self, args):
        q = args.strip()
        if not q:
            logger.warning('use <steam_id|nickname>')
            return
        sid = self.player_store.find(q) or q
        self._switch_to_player(sid)

    def _cmd_summary(self, args):
        sid = (self.player_store.find(args.strip()) or args.strip()
               or self.current_steam_id)
        if not sid:
            logger.warning('Нет активного игрока')
            return
        from src.services.report import build_short_report
        logger.info(build_short_report(self, sid))

    def _cmd_full_report(self, args):
        sid = (self.player_store.find(args.strip()) or args.strip()
               or self.current_steam_id)
        if not sid:
            logger.warning('Нет активного игрока')
            return
        from src.services.report import build_full_report
        for line in build_full_report(self, sid).splitlines():
            logger.info(line)

    def _cmd_countries(self, args):
        if not self.current_steam_id:
            logger.warning('нет игрока')
            return
        dp = self.window.deep_page
        if not dp._match_data:
            logger.warning('нет match_data')
            return
        counts = {}
        for entry in dp._match_data:
            for p in entry['teammates'] + entry['enemies']:
                c = (p.get('country') or '?').lower()
                counts[c] = counts.get(c, 0) + 1
        for c, n in sorted(counts.items(), key=lambda x: -x[1])[:30]:
            logger.info(f'  {c}: {n}')

    def _audit_all(self):
        logger.info('══════════ FULL AUDIT ══════════')
        dp = self.window.deep_page
        logger.info(f'_match_data: {len(dp._match_data)}')
        logger.info(f'Chart player: {len(dp.comparison._player_data)}')
        logger.info(f'Chart teammates: {len(dp.comparison._teammates_data)}')
        logger.info(f'Chart enemies: {len(dp.comparison._enemies_data)}')

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
        dlg.setWindowTitle('Ошибка')
        dlg.resize(900, 500)
        layout = QVBoxLayout(dlg)
        edit = QTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(f'{e}\n\n{tb}')
        layout.addWidget(edit)
        btn = QPushButton('Закрыть')
        btn.clicked.connect(dlg.reject)
        layout.addWidget(btn)
        dlg.exec()
        sys.exit(1)


if __name__ == '__main__':
    main()
