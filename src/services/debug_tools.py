import asyncio
import logging
import traceback

logger = logging.getLogger('faceit_analytics')


def _log(msg, level='info'):
    getattr(logger, level)(msg)


# ─────────────── HEALTH CHECK ───────────────
def health_check(app, args):
    _log('══════════ HEALTH CHECK ══════════')
    _log('── 1. Резолверы ──')
    try:
        from src.services.player_elo_resolver import get_elo_resolver
        r = get_elo_resolver()
        ok = sum(1 for v in r._cache.values() if v.get('elo'))
        _log(f'  ELO resolver: {len(r._cache)} (с ELO: {ok})')
    except Exception as e:
        _log(f'  ELO ERROR: {e}', 'error')

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
        _log(f'  Всего: {pr.total}, рабочих: {pr.count}, спящих: {pr.sleeping}')
        _log(f'  ok={st["ok"]}, fail={st["fail"]}, sleep={st["sleep"]}')
    except Exception as e:
        _log(f'  Proxy ERROR: {e}', 'error')

    _log('── 3. PlayerStore ──')
    try:
        from src.core.player_store import get_player_store
        ps = get_player_store()
        wd = sum(1 for r in ps._data.values() if r.get('has_deep'))
        _log(f'  Игроков: {len(ps._data)}, с deep: {wd}')
    except Exception as e:
        _log(f'  Store ERROR: {e}', 'error')

    _log('── 4. In-memory ──')
    _log(f'  _player_cache: {len(app._player_cache)}')
    _log(f'  _deep_cache: {len(app._deep_cache)}')

    _log('── 5. БД ──')
    try:
        p = app.db.conn.execute('SELECT COUNT(*) FROM players').fetchone()[0]
        m = app.db.conn.execute('SELECT COUNT(*) FROM matches').fetchone()[0]
        _log(f'  players: {p}, matches: {m}')
    except Exception as e:
        _log(f'  DB ERROR: {e}', 'error')

    _log('── 6. Файлы данных ──')
    from src.config import DATA_DIR
    for f in ['settings.json', 'players_index.json', 'player_elo_cache.json',
              'country_cache.json', 'proxies.txt', 'proxies_working.txt']:
        p = DATA_DIR / f
        sz = p.stat().st_size if p.exists() else 0
        _log(f'  {"✅" if p.exists() else "❌"} {f} ({sz} байт)')
    _log('══════════ HEALTH CHECK ЗАВЕРШЁН ══════════')


# ─────────────── PROBE SOURCES ───────────────
async def _probe_all(app, steam_id):
    ps = app.player_service
    sources = [
        ('steam', ps.steam.fetch_player),
        ('faceit', ps.faceit.fetch_player),
        ('cswatch', ps.cswatch.fetch_player),
        ('csstats', ps.csstats.fetch_player),
    ]
    for name, fn in sources:
        try:
            r = await fn(steam_id)
            if isinstance(r, dict):
                filled = {k: v for k, v in r.items()
                          if v not in ('', 0, None, False, [])}
                _log(f'  [{name}] {len(filled)}/{len(r)}: '
                     f'{list(filled.keys())[:12]}')
            else:
                _log(f'  [{name}] вернул {type(r).__name__}', 'warning')
        except Exception as e:
            _log(f'  [{name}] ERROR: {e}', 'error')
    try:
        r = app.csrep.fetch_player(steam_id)
        if isinstance(r, dict):
            filled = {k: v for k, v in r.items()
                      if v not in ('', 0, None, False, [])}
            _log(f'  [csrep] {len(filled)}: {list(filled.keys())}')
    except Exception as e:
        _log(f'  [csrep] ERROR: {e}', 'error')
    try:
        from src.data_sources.faceitanalyser import FaceitAnalyserSource
        fa = FaceitAnalyserSource(app.cache)
        r = await fa.fetch_player(steam_id)
        if isinstance(r, dict):
            filled = {k: v for k, v in r.items()
                      if v not in ('', 0, None, False, [])}
            _log(f'  [faceitanalyser] {len(filled)}: {list(filled.keys())}')
        else:
            _log(f'  [faceitanalyser] пусто', 'warning')
    except Exception as e:
        _log(f'  [faceitanalyser] ERROR: {e}', 'error')


def probe_sources(app, args):
    steam_id = (args.split()[0] if args.strip()
                else app.current_steam_id or '')
    if not steam_id:
        _log('probe_sources <steam_id>', 'warning')
        return
    _log('══════════ PROBE SOURCES ══════════')
    _log(f'steam_id: {steam_id}')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_probe_all(app, steam_id))
    except Exception as e:
        _log(f'ERROR: {e}', 'error')
    finally:
        loop.close()
    _log('══════════ PROBE ЗАВЕРШЁН ══════════')


# ─────────────── REPORT COVERAGE ───────────────
def report_coverage(app, args):
    sid = (args.split()[0] if args.strip()
           else app.current_steam_id or '')
    if not sid:
        _log('report_coverage <steam_id>', 'warning')
        return
    _log('══════════ COVERAGE ══════════')
    _log(f'steam_id: {sid}')
    _log('── QUICK ──')
    cached = app._player_cache.get(sid)
    if not cached:
        _log('  quick нет в памяти')
    else:
        d = cached[1]
        for k in ['nickname', 'faceit_id', 'faceit_level', 'faceit_elo',
                  'country', 'matches_total', 'win_rate', 'avg_kd',
                  'reputation_score', 'risk_level', 'trust_score',
                  'kd', 'adr']:
            v = d.get(k)
            status = '✅' if v not in (None, '', 0, False, []) else '❌'
            _log(f'  {status} {k}: {str(v)[:60]}')
    _log('── DEEP ──')
    deep = app._deep_cache.get(sid)
    if not deep:
        _log('  deep нет в памяти')
    else:
        _, fr, matches = deep
        _log(f'  матчей: {len(matches)}')
        md = fr.get('match_data', [])
        _log(f'  match_data: {len(md)}')
        concl = fr.get('conclusions', {})
        _log(f'  conclusions: {list(concl.keys())}')
    _log('══════════ COVERAGE ЗАВЕРШЁН ══════════')


# ─────────────── DEEP COUNTS ───────────────
def deep_counts(app, args):
    sid = app.current_steam_id
    if not sid:
        _log('нет игрока', 'warning')
        return
    _log('══════════ DEEP COUNTS ══════════')
    cached = app.cache.get('faceit_matches', sid) or []
    _log(f'1. Кэш матчей: {len(cached)}')

    with_details = 0
    for m in cached:
        mid = m.get('match_id') or m.get('id')
        if mid and app.cache.get('match_players', mid):
            with_details += 1
    _log(f'2. Из них с деталями: {with_details}')

    deep = app._deep_cache.get(sid)
    if deep:
        _, fr, matches = deep
        _log(f'3. _deep_cache matches: {len(matches)}')
        md = fr.get('match_data', [])
        _log(f'4. _deep_cache match_data: {len(md)}')
        _log(f'5. deep limit: {fr.get("match_limit", "?")}')
    else:
        _log('3-5. _deep_cache пуст')

    dp = app.window.deep_page
    _log(f'6. DeepPage._match_data: {len(dp._match_data)}')
    if dp._match_data:
        only_self = sum(1 for e in dp._match_data
                         if not e.get('teammates') and not e.get('enemies'))
        with_d = len(dp._match_data) - only_self
        _log(f'    ├─ с деталями: {with_d}')
        _log(f'    └─ только self: {only_self}')
    _log(f'7. Chart player buckets: '
         f'{sorted(dp.comparison._player_data.keys())}')
    _log(f'8. Chart teammates buckets (первые 15): '
         f'{sorted(dp.comparison._teammates_data.keys())[:15]}')
    _log(f'9. Chart enemies buckets (первые 15): '
         f'{sorted(dp.comparison._enemies_data.keys())[:15]}')
    _log(f'10. MatchesPage: {app.window.matches_page.table.rowCount()}')
    _log('══════════════════════════════════')


# ─────────────── ELO / PROXY ───────────────
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


def proxy_status(args=''):
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    st = pr.stats()
    _log(f'Прокси: рабочих {pr.count}, спящих {pr.sleeping}, '
         f'всего {pr.total}')
    _log(f'  ok={st["ok"]}, fail={st["fail"]}, sleep={st["sleep"]}')


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


def proxy_stats(args=''):
    proxy_status(args)


# ─────────────── CHECK MATCH ───────────────
def check_match(app, args):
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
        _log(f"      {p.get('nickname','?'):20} "
             f"faction={p.get('faction','')} "
             f"K/D/A={p.get('kills',0)}/{p.get('deaths',0)}/{p.get('assists',0)}")
    if not players:
        _log('  [2] HTML fallback:')
        players2 = fetch_room_players_sync(mid)
        _log(f'      игроков: {len(players2)}')


def bucket_players(app, args):
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
    seen = {}
    for entry in dp._match_data:
        for p in entry['teammates'] + entry['enemies']:
            pe = int(p.get('player_elo', 0) or 0)
            if bucket <= pe < bucket + 25:
                k = p.get('player_id') or p.get('nickname')
                if k and k not in seen:
                    seen[k] = (p.get('nickname', '?'), pe)
    for k, (nick, elo) in sorted(seen.items(), key=lambda x: x[1][1]):
        _log(f'  {nick:25} ELO={elo:5}')
    _log(f'  всего: {len(seen)}')


def retry_failed(app, args):
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
    _log(f'матчей без деталей: {cleared}')
    _log('Запусти deep снова — попробуем дозагрузить')


def agg_check(app, args):
    dp = app.window.deep_page
    _log('── Агрегатор ──')
    _log(f'  _match_data: {len(dp._match_data)}')
    _log(f'  player buckets: {sorted(dp.comparison._player_data.keys())}')
    _log(f'  teammate buckets: {sorted(dp.comparison._teammates_data.keys())}')
    _log(f'  enemy buckets: {sorted(dp.comparison._enemies_data.keys())}')


def faceit_debug(app, args):
    steam_id = (args.split()[0] if args.strip()
                else app.current_steam_id or '')
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


def run_full_debug(app, args):
    probe_sources(app, args)
