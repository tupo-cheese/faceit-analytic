import logging

logger = logging.getLogger('faceit_analytics')


def _fmt(v, default='—'):
    if v in (None, '', 0, [], {}):
        return default
    return v


def build_full_report(app, steam_id):
    """Полнотекстовый отчёт по игроку из всех кэшей + БД."""
    from src.core.player_store import get_player_store
    store = get_player_store()
    rec = store.get(steam_id)

    lines = []
    lines.append('═' * 70)
    lines.append(f'  ПОЛНЫЙ ОТЧЁТ ПО ИГРОКУ')
    lines.append('═' * 70)
    lines.append(f'Steam ID  : {steam_id}')
    lines.append(f'Ник       : {_fmt(rec.get("nickname"))}')
    lines.append(f'FACEIT ID : {_fmt(rec.get("faceit_id"))}')
    lines.append(f'FACEIT LVL: {_fmt(rec.get("faceit_level"))}')
    lines.append(f'FACEIT ELO: {_fmt(rec.get("faceit_elo"))}')
    lines.append(f'Страна    : {_fmt(rec.get("country"))}')
    lines.append(f'Загружен  : {_fmt(rec.get("last_loaded"))}')
    lines.append(f'Deep      : {rec.get("has_deep", False)} '
                 f'({rec.get("deep_matches", 0)} матчей, {rec.get("last_deep", "—")})')

    # quick
    cached = app._player_cache.get(steam_id)
    if cached:
        data = cached[1]
        lines.append('')
        lines.append('── QUICK SUMMARY ──')
        for k in sorted(data.keys()):
            v = data[k]
            if isinstance(v, dict):
                lines.append(f'  {k}:')
                for k2, v2 in list(v.items())[:20]:
                    lines.append(f'    {k2} = {v2}')
            elif isinstance(v, list):
                lines.append(f'  {k}: [{len(v)} элементов] {v[:5]}')
            else:
                if v not in ('', None, 0, False):
                    lines.append(f'  {k} = {v}')

    # deep
    deep = app._deep_cache.get(steam_id)
    if deep:
        _, full_result, matches = deep
        lines.append('')
        lines.append('── DEEP АНАЛИТИКА ──')
        inner = full_result.get('deep_result', {}) if isinstance(full_result, dict) else {}
        summary = inner.get('summary', {}) if isinstance(inner, dict) else {}
        # если пусто — считаем из match_data
        if not summary:
            md = full_result.get('match_data', [])
            if md:
                try:
                    from src.core.analytics.deep import DeepAnalyzer
                    summary = DeepAnalyzer().analyze({}, matches).get('summary', {})
                except Exception:
                    pass
        lines.append(f'  Матчей всего: {summary.get("matches", 0)}')
        lines.append(f'  Побед: {summary.get("wins", 0)} ({summary.get("winrate", 0)}%)')
        lines.append(f'  K/D total: {summary.get("kd_total", 0)} '
                     f'avg: {summary.get("kd_avg", 0)} '
                     f'med: {summary.get("kd_median", 0)}')
        lines.append(f'  ADR avg: {summary.get("adr_avg", 0)} '
                     f'med: {summary.get("adr_median", 0)}')
        lines.append(f'  HS% avg: {summary.get("hs_avg", 0)}')
        lines.append(f'  ELO: {summary.get("elo_min", 0)}–{summary.get("elo_max", 0)} '
                     f'(avg {summary.get("elo_avg", 0)})')

        # conclusions
        conclusions = full_result.get('conclusions') or {}
        if not conclusions:
            try:
                from src.core.analytics.conclusions import DeepConclusions
                md = full_result.get('match_data', [])
                if md:
                    conclusions = DeepConclusions().analyze(md)
            except Exception:
                pass
        if conclusions:
            lines.append('')
            lines.append('── ВЫВОДЫ ──')
            own = conclusions.get('own_performance', {})
            if own:
                lines.append(f'  Своя игра: WR {own.get("winrate")}%, '
                             f'K/D {own.get("kd_avg")}, ADR {own.get("adr_avg")}')
            ec = conclusions.get('elo_context', {})
            if ec:
                lines.append(f'  ELO контекст: мой {ec.get("my_elo_min")}–{ec.get("my_elo_max")}, '
                             f'лобби {ec.get("lobby_elo_min")}–{ec.get("lobby_elo_max")}')
            bp = conclusions.get('by_party', {})
            if bp:
                lines.append(f'  Пати: {dict(bp)}')
            ti = conclusions.get('teammate_impact', {})
            if ti.get('best'):
                lines.append(f'  Лучшие тиммейты:')
                for t in ti['best'][:5]:
                    lines.append(f'    {t.get("nick")}: WR {t.get("winrate")}% '
                                 f'({t.get("matches")} игр)')
            ei = conclusions.get('enemy_impact', {})
            if ei.get('toughest'):
                lines.append(f'  Сложные враги:')
                for t in ei['toughest'][:3]:
                    lines.append(f'    {t.get("nick")}: Loss {t.get("loss_rate")}%')

        # matches list
        lines.append('')
        lines.append(f'── МАТЧИ ({len(matches)}) ──')
        for m in matches[:10]:
            lines.append(f'  {m.get("date", 0)} | ELO {m.get("elo", 0)} | '
                         f'{m.get("map_name", "")} | '
                         f'K/D/A {m.get("kills", 0)}/{m.get("deaths", 0)}/{m.get("assists", 0)} | '
                         f'ADR {m.get("adr", 0)} | W {"да" if m.get("result") else "нет"}')
        if len(matches) > 10:
            lines.append(f'  ... и ещё {len(matches) - 10}')

    # БД
    try:
        db_player = app.db.get_player(steam_id)
        if db_player and db_player.get('data'):
            lines.append('')
            lines.append('── ИЗ БД ──')
            lines.append(f'  nickname: {db_player.get("nickname")}')
            lines.append(f'  faceit_id: {db_player.get("faceit_id")}')
            lines.append(f'  last_updated: {db_player.get("last_updated")}')
    except Exception as e:
        lines.append(f'  БД err: {e}')

    lines.append('')
    lines.append('═' * 70)
    return '\n'.join(lines)


def build_short_report(app, steam_id):
    """Краткая сводка в одну простыню."""
    rec = __import__('src.core.player_store', fromlist=['get_player_store']).get_player_store().get(steam_id)
    parts = [f'{rec.get("nickname", "?")} [{steam_id}]']
    if rec.get('faceit_elo'):
        parts.append(f'ELO {rec["faceit_elo"]}')
    if rec.get('faceit_level'):
        parts.append(f'LVL {rec["faceit_level"]}')
    cached = app._player_cache.get(steam_id)
    if cached:
        d = cached[1]
        if d.get('win_rate'):
            parts.append(f'WR {d["win_rate"]}')
        if d.get('avg_kd'):
            parts.append(f'K/D {d["avg_kd"]}')
        if d.get('adr'):
            parts.append(f'ADR {d["adr"]}')
        if d.get('cswatch_risk'):
            parts.append(f'risk {d["cswatch_risk"]}')
    deep = app._deep_cache.get(steam_id)
    if deep:
        s = deep[1].get('summary', {})
        parts.append(f'deep: {s.get("matches", 0)} матчей')
    return ' | '.join(parts)
