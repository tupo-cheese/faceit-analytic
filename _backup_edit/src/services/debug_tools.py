import asyncio
import logging
import traceback

logger = logging.getLogger('faceit_analytics')


def _log(msg, level='info'):
    getattr(logger, level)(msg)


# ─────────────────────────────────────────────────────────────────
# HEALTH CHECK — без сети
# ─────────────────────────────────────────────────────────────────
def health_check(app, args):
    _log('══════════ HEALTH CHECK ══════════')
    _log('── 1. Резолверы ──')
    try:
        from src.services.player_elo_resolver import get_elo_resolver
        r = get_elo_resolver()
        ok = sum(1 for v in r._cache.values() if v.get('elo'))
        _log(f'  ELO resolver: {len(r._cache)} записей (с ELO: {ok})')
    except Exception as e:
        _log(f'  ELO resolver ERROR: {e}', 'error')

    try:
        from src.services.country_resolver import get_resolver
        cr = get_resolver()
        ok = sum(1 for v in cr._cache.values() if v)
        _log(f'  Country resolver: {len(cr._cache)} (заполнено: {ok})')
    except Exception as e:
        _log(f'  Country ERROR: {e}', 'error')

    _log('── 2. Прокси ──')
    try:
        from src.services.proxy_rotator import get_proxy_rotator
        pr = get_proxy_rotator()
        st = pr.stats()
        _log(f'  Всего: {pr.total}, рабочих: {pr.count}, '
             f'спящих: {pr.sleeping}')
        _log(f'  ok={st["ok"]}, fail={st["fail"]}, sleep={st["sleep"]}')
    except Exception as e:
        _log(f'  Proxy ERROR: {e}', 'error')

    _log('── 3. PlayerStore ──')
    try:
        from src.core.player_store import get_player_store
        ps = get_player_store()
        _log(f'  Игроков в истории: {len(ps._data)}')
        with_deep = sum(1 for r in ps._data.values() if r.get('has_deep'))
        _log(f'  Из них с deep: {with_deep}')
    except Exception as e:
        _log(f'  PlayerStore ERROR: {e}', 'error')

    _log('── 4. In-memory кэши ──')
    _log(f'  _player_cache: {len(app._player_cache)}')
    _log(f'  _deep_cache: {len(app._deep_cache)}')

    _log('── 5. БД ──')
    try:
        players = app.db.conn.execute(
            'SELECT COUNT(*) FROM players').fetchone()[0]
        matches = app.db.conn.execute(
            'SELECT COUNT(*) FROM matches').fetchone()[0]
        _log(f'  players: {players}, matches: {matches}')
    except Exception as e:
        _log(f'  DB ERROR: {e}', 'error')

    _log('── 6. Зарегистрированные команды ──')
    commands = [
        'help', 'clear', 'clear_cache', 'clear_matches', 'audit_all',
        'dump_elo', 'deep', 'quick', 'elo_cache', 'debug_all', 'faceit_debug',
        'elo_check', 'agg_check', 'proxy_status', 'proxy_reload', 'proxy_verify',
        'players', 'use', 'summary', 'full_report', 'refresh', 'load_more',
        'countries', 'health_check', 'probe_sources', 'report_coverage',
    ]
    src = (ROOT := __import__('pathlib').Path(r'F:\faceit_analytic')) / 'src' / 'app.py'
    try:
        text = src.read_text(encoding='utf-8')
        for cmd in commands:
            marker = f"name == '{cmd}'"
            status = '✅' if marker in text else '❌'
            _log(f'  {status} {cmd}')
    except Exception as e:
        _log(f'  app.py read ERROR: {e}', 'error')

    _log('── 7. Файлы данных ──')
    from src.config import DATA_DIR
    for f in ['settings.json', 'players_index.json',
              'player_elo_cache.json', 'country_cache.json',
              'proxies.txt', 'proxies_working.txt']:
        p = DATA_DIR / f
        sz = p.stat().st_size if p.exists() else 0
        _log(f'  {"✅" if p.exists() else "❌"} {f} ({sz} байт)')
    _log('══════════ HEALTH CHECK ЗАВЕРШЁН ══════════')


# ─────────────────────────────────────────────────────────────────
# PROBE SOURCES — с сетью
# ─────────────────────────────────────────────────────────────────
async def _probe_all(app, steam_id):
    ps = app.player_service
    sources = [
        ('steam', ps.steam.fetch_player, False),
        ('faceit', ps.faceit.fetch_player, False),
        ('cswatch', ps.cswatch.fetch_player, False),
        ('csstats', ps.csstats.fetch_player, False),
    ]
    for name, fn, _ in sources:
        try:
            r = await fn(steam_id)
            if isinstance(r, dict):
                filled = {k: v for k, v in r.items()
                          if v not in ('', 0, None, False, [])}
                _log(f'  [{name}] OK {len(filled)}/{len(r)}: '
                     f'{list(filled.keys())[:15]}')
                missing = [k for k in r if k not in filled]
                if missing:
                    _log(f'    пусто: {missing[:10]}')
            else:
                _log(f'  [{name}] вернул {type(r).__name__}', 'warning')
        except Exception as e:
            _log(f'  [{name}] ERROR: {e}', 'error')

    # csrep синхронный
    try:
        r = app.csrep.fetch_player(steam_id)
        if isinstance(r, dict):
            filled = {k: v for k, v in r.items()
                      if v not in ('', 0, None, False, [])}
            _log(f'  [csrep] OK {len(filled)}: {list(filled.keys())}')
    except Exception as e:
        _log(f'  [csrep] ERROR: {e}', 'error')

    # faceitanalyser
    try:
        from src.data_sources.faceitanalyser import FaceitAnalyserSource
        fa = FaceitAnalyserSource(app.cache)
        r = await fa.fetch_player(steam_id)
        if isinstance(r, dict):
            filled = {k: v for k, v in r.items()
                      if v not in ('', 0, None, False, [])}
            _log(f'  [faceitanalyser] OK {len(filled)}: {list(filled.keys())}')
        else:
            _log(f'  [faceitanalyser] пусто', 'warning')
    except Exception as e:
        _log(f'  [faceitanalyser] ERROR: {e}', 'error')


def probe_sources(app, args):
    steam_id = (args.split()[0] if args.strip() else '') or app.current_steam_id or ''
    if not steam_id:
        _log('probe_sources <steam_id> — укажи steam_id', 'warning')
        return
    _log('══════════ PROBE SOURCES ══════════')
    _log(f'steam_id: {steam_id}')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    merged = {}
    try:
        merged = loop.run_until_complete(_probe_and_merge(app, steam_id))
    except Exception as e:
        _log(f'ERROR: {e}', 'error')
        _log(traceback.format_exc(), 'error')
    finally:
        loop.close()
    if merged:
        # обновляем _player_cache
        cached = app._player_cache.get(steam_id)
        base = cached[1] if cached else {}
        for k, v in merged.items():
            if v not in ('', 0, None, False, []):
                base[k] = v
        import time as _t
        app._player_cache[steam_id] = (_t.time(), base)
        _log(f'✅ _player_cache обновлён ({len(base)} полей)')
        try:
            app.player_store.upsert(steam_id,
                                     nickname=base.get('nickname', ''),
                                     faceit_id=base.get('faceit_id', ''),
                                     faceit_elo=base.get('faceit_elo', 0),
                                     faceit_level=base.get('faceit_level', 0),
                                     country=base.get('country', ''))
            app.window.quick_page.card.set_data(base)
            app.window.quick_page.set_quick_stats(base)
        except Exception:
            pass
    _log('══════════ PROBE ЗАВЕРШЁН ══════════')


async def _probe_and_merge(app, steam_id):
    ps = app.player_service
    merged = {}
    for name, fn in [('steam', ps.steam.fetch_player),
                     ('faceit', ps.faceit.fetch_player),
                     ('cswatch', ps.cswatch.fetch_player),
                     ('csstats', ps.csstats.fetch_player)]:
        try:
            r = await fn(steam_id)
            if isinstance(r, dict):
                filled = {k: v for k, v in r.items()
                          if v not in ('', 0, None, False, [])}
                _log(f'  [{name}] OK {len(filled)}/{len(r)}: '
                     f'{list(filled.keys())[:15]}')
                missing = [k for k in r if k not in filled]
                if missing:
                    _log(f'    пусто: {missing[:10]}')
                for k, v in filled.items():
                    merged[k] = v
        except Exception as e:
            _log(f'  [{name}] ERROR: {e}', 'error')
    try:
        r = app.csrep.fetch_player(steam_id)
        if isinstance(r, dict):
            for k, v in r.items():
                if k not in ('steam_id', 'source') and v not in ('', 0, None, False, []):
                    merged[k] = v
    except Exception:
        pass
    try:
        from src.data_sources.faceitanalyser import FaceitAnalyserSource
        fa = FaceitAnalyserSource(app.cache)
        r = await fa.fetch_player(steam_id)
        if isinstance(r, dict):
            filled = {k: v for k, v in r.items()
                      if v not in ('', 0, None, False, [])}
            _log(f'  [faceitanalyser] OK {len(filled)}: {list(filled.keys())}')
            for k, v in filled.items():
                if k not in ('raw_html_len',):
                    merged[k] = v
        else:
            _log(f'  [faceitanalyser] пусто', 'warning')
    except Exception as e:
        _log(f'  [faceitanalyser] ERROR: {e}', 'error')
    return merged


# ─────────────────────────────────────────────────────────────────
# REPORT COVERAGE — что у нас есть vs что ожидаем
# ─────────────────────────────────────────────────────────────────
def report_coverage(app, args):
    steam_id = (args.split()[0] if args.strip() else '') or app.current_steam_id or ''
    if not steam_id:
        _log('report_coverage <steam_id>', 'warning')
        return
    _log('══════════ COVERAGE ══════════')
    _log(f'steam_id: {steam_id}')

    _log('── QUICK ──')
    cached = app._player_cache.get(steam_id)
    if not cached:
        _log('  quick нет в памяти')
    else:
        d = cached[1]
        expected = [
            'nickname', 'avatar_url', 'faceit_id', 'faceit_level', 'faceit_elo',
            'country', 'steam_url', 'faceit_url',
            'matches_total', 'win_rate', 'avg_kd', 'avg_hs',
            'reputation_score', 'risk_level', 'vac_banned', 'game_banned',
            'trust_score', 'kd', 'adr', 'rating',
        ]
        for k in expected:
            v = d.get(k)
            status = '✅' if v not in (None, '', 0, False, []) else '❌'
            _log(f'  {status} {k}: {str(v)[:60]}')
        extra = [k for k in d if k not in expected]
        _log(f'  доп. поля: {extra[:20]}')

    _log('── DEEP ──')
    deep = app._deep_cache.get(steam_id)
    if not deep:
        _log('  deep нет в памяти')
    else:
        _, dr, matches = deep
        s = dr.get('summary', {})
        _log(f'  матчей: {len(matches)}')
        _log(f'  summary keys: {list(s.keys())}')
        concl = dr.get('_conclusions', {})
        _log(f'  conclusions: {list(concl.keys())}')
        if concl:
            for k, v in concl.items():
                if isinstance(v, dict):
                    _log(f'    {k}: {len(v)} записей')
                else:
                    _log(f'    {k}: {v}')
    _log('══════════ COVERAGE ЗАВЕРШЁН ══════════')


# ─────────────────────────────────────────────────────────────────
# остальные команды из предыдущей версии
# ─────────────────────────────────────────────────────────────────
def proxy_stats(args=''):
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    st = pr.stats()
    _log(f'Прокси: рабочих {pr.count}, спящих {pr.sleeping}, '
         f'всего {pr.total}')
    _log(f'  ok={st["ok"]}, fail={st["fail"]}, sleep={st["sleep"]}')


def proxy_status(args=''):
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    _log(f'Прокси: {pr.count} рабочих, спящих {pr.sleeping}, '
         f'всего {pr.total}')


def proxy_reload(args=''):
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    pr.reload()
    _log(f'Прокси перезагружены: {pr.total} строк')


def proxy_verify(args=''):
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    if not pr._all:
        pr.reload()
    if not pr._all:
        _log('proxies.txt пуст', 'warning')
        return
    n = pr.verify()
    _log(f'Проверка: {n} рабочих из {pr.total}')


def run_full_debug(app, args):
    steam_id = (args.split()[0] if args.strip() else '') or app.current_steam_id or ''
    if not steam_id:
        _log('debug_all <steam_id>', 'warning')
        return
    _log('══════════ ПОЛНЫЙ ДЕБАГ ══════════')
    _log(f'steam_id: {steam_id}')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_probe_all(app, steam_id))
    except Exception as e:
        _log(f'ERROR: {e}', 'error')
    finally:
        loop.close()
    _log('══════════ ДЕБАГ ЗАВЕРШЁН ══════════')


def faceit_debug(app, args):
    steam_id = (args.split()[0] if args.strip() else '') or app.current_steam_id or ''
    if not steam_id:
        _log('faceit_debug <steam_id>', 'warning')
        return
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    _log(f'── faceit_debug {steam_id} ──')
    _log(f'  Прокси: {pr.count}/{pr.total}')
    cached = app.cache.get('faceit_player', steam_id)
    if cached:
        _log(f'  faceit_id={cached.get("faceit_id", "")}')
        _log(f'  nickname={cached.get("nickname", "")}')
        _log(f'  elo={cached.get("faceit_elo", 0)}')
    else:
        _log('  кэш пуст')


def check_match(app, args):
    """check_match <match_id> — сырые данные одного матча."""
    mid = args.strip()
    if not mid:
        _log('check_match <match_id>', 'warning')
        return
    from src.data_sources.faceit_stats import FaceitMatchStats
    from src.services.match_room_parser import fetch_room_players_sync
    _log(f'── check_match {mid} ──')
    _log('  [1] API:')
    players = FaceitMatchStats.fetch_match(mid, with_country=False)
    _log(f'      игроков: {len(players)}')
    for p in players[:20]:
        _log(f"      {p.get('nickname','?'):20} faction={p.get('faction','')} "
             f"K/D/A={p.get('kills',0)}/{p.get('deaths',0)}/{p.get('assists',0)} "
             f"ADR={p.get('adr',0)}")
    if not players:
        _log('  [2] HTML fallback:')
        players2 = fetch_room_players_sync(mid)
        _log(f'      игроков: {len(players2)}')
        for p in players2[:20]:
            _log(f"      {p.get('nickname','?'):20} faction={p.get('faction','')}")


def bucket_players(app, args):
    """bucket_players <bucket_elo> — показать игроков в бакете."""
    try:
        bucket = int(args.strip())
    except Exception:
        _log('bucket_players <elo>', 'warning')
        return
    dp = app.window.deep_page
    if not dp._match_data:
        _log('нет match_data', 'warning')
        return
    _log(f'── Игроки в бакете {bucket}-{bucket+24} ──')
    from src.services.player_elo_resolver import get_elo_resolver
    r = get_elo_resolver()
    seen = {}
    for entry in dp._match_data:
        for p in entry['teammates'] + entry['enemies']:
            pe = int(p.get('player_elo', 0) or 0)
            if bucket <= pe < bucket + 25:
                k = p.get('player_id') or p.get('nickname')
                if k and k not in seen:
                    source = r._cache.get(k.lower(), {}).get('source', '?')
                    seen[k] = (p.get('nickname', '?'), pe, source)
    for k, (nick, elo, src) in sorted(seen.items(), key=lambda x: x[1][1]):
        _log(f'  {nick:25} ELO={elo:5} src={src}')
    _log(f'  всего: {len(seen)}')


def deep_counts(app, args):
    """Сверяет счётчики: matches vs match_data vs cached players."""
    sid = app.current_steam_id
    if not sid:
        _log('нет игрока', 'warning')
        return
    _log('══════════ DEEP COUNTS ══════════')
    cached_matches = app.cache.get('faceit_matches', sid) or []
    _log(f'1. Кэш матчей (faceit_matches): {len(cached_matches)}')

    # матчи с деталями в кэше
    with_details = 0
    for m in cached_matches:
        mid = m.get('match_id') or m.get('id')
        if mid and app.cache.get('match_players', mid):
            with_details += 1
    _log(f'2. Из них с деталями (match_players): {with_details}')

    # matches в in-memory deep cache
    deep = app._deep_cache.get(sid)
    if deep:
        _, full_result, matches = deep
        _log(f'3. _deep_cache matches: {len(matches)}')
        md = full_result.get('match_data', [])
        _log(f'4. _deep_cache match_data: {len(md)}')
        _log(f'5. deep limit: {full_result.get("match_limit", "?")}')

    # на графике
    dp = app.window.deep_page
    _log(f'6. DeepPage._match_data: {len(dp._match_data)}')
    _log(f'7. Chart player: {len(dp.comparison._player_data)}')
    _log(f'8. Chart teammates: {len(dp.comparison._teammates_data)}')
    _log(f'9. Chart enemies: {len(dp.comparison._enemies_data)}')

    # matches page
    _log(f'10. MatchesPage: {app.window.matches_page.table.rowCount()}')
    _log('══════════════════════════════════')


def retry_failed(app, args):
    """retry_failed — сбросить кэш для матчей без данных."""
    sid = app.current_steam_id
    if not sid:
        _log('нет игрока', 'warning')
        return
    matches = app.cache.get('faceit_matches', sid) or []
    cleared = 0
    for m in matches:
        mid = m.get('match_id') or m.get('id')
        if mid and not app.cache.get('match_players', mid):
            cleared += 1
    _log(f'матчей без деталей: {cleared} (кэш уже пуст)')
    _log('Запусти deep снова — попробуем дозагрузить')


def elo_check(args):
    parts = args.split()
    if not parts:
        _log('elo_check <player_id> [nickname]', 'warning')
        return
    pid = parts[0]
    nick = parts[1] if len(parts) > 1 else ''
    from src.services.player_elo_resolver import get_elo_resolver
    r = get_elo_resolver()
    _log(f'ELO check pid={pid[:20]} nick={nick}')
    key, result = r._fetch_one((nick, pid))
    _log(f'  key={key}')
    _log(f'  result={result}')


def agg_check(app, args):
    dp = app.window.deep_page
    _log('── Агрегатор ──')
    _log(f'  _match_data: {len(dp._match_data)}')
    if dp.comparison._player_data:
        _log(f'  player buckets: {sorted(dp.comparison._player_data.keys())}')
    if dp.comparison._teammates_data:
        _log(f'  teammate buckets: {sorted(dp.comparison._teammates_data.keys())}')
    if dp.comparison._enemies_data:
        _log(f'  enemy buckets: {sorted(dp.comparison._enemies_data.keys())}')
