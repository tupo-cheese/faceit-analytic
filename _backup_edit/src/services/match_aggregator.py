import asyncio
import logging
import statistics
import concurrent.futures
from collections import defaultdict, Counter

logger = logging.getLogger('faceit_analytics')


class MatchAggregator:

    def __init__(self, cache, db, elo_step=50):
        self.cache = cache
        self.db = db
        self.elo_step = elo_step
        self.on_progress = None
        self.on_match_collected = None   # callback(result) — сразу как матч готов
        self.max_workers = 128

    def _collect_one(self, match, my_player_id):
        from src.data_sources.faceit_stats import FaceitMatchStats
        mid = match.get('match_id') or match.get('id')
        if not mid:
            return (None, 'no_id')
        cached = self.cache.get('match_players', mid)
        if cached:
            players = cached
        else:
            players = FaceitMatchStats.fetch_match(mid, with_country=False)
            if not players:
                try:
                    from src.services.match_room_parser import fetch_room_players_sync
                    players = fetch_room_players_sync(mid)
                except Exception:
                    pass
            if players:
                self.cache.set('match_players', mid, players)
        if not players:
            # fallback: матч без деталей — используем данные самого игрока
            # из исходного матча (kills/deaths/adr/elo уже есть)
            me_fallback = {
                'player_id': my_player_id,
                'nickname': match.get('nickname', ''),
                'faction': '',
                'country': '',
                'kills': int(match.get('kills', 0) or 0),
                'deaths': int(match.get('deaths', 0) or 0),
                'assists': int(match.get('assists', 0) or 0),
                'kd_ratio': float(match.get('kd_ratio', 0) or 0),
                'kr_ratio': float(match.get('kr_ratio', 0) or 0),
                'adr': float(match.get('adr', 0) or 0),
                'headshots_percent': float(match.get('headshots_percent', 0) or 0),
                'mvps': int(match.get('mvps', 0) or 0),
                'triple_kills': int(match.get('triple_kills', 0) or 0),
                'quadro_kills': int(match.get('quadro_kills', 0) or 0),
                'penta_kills': int(match.get('penta_kills', 0) or 0),
                'rounds': int(match.get('rounds', 0) or 0),
                'rating': 1.0,
                'swing': 0.0,
                'result': int(match.get('result', 0) or 0),
            }
            return ({
                'match_id': mid,
                'elo': int(match.get('elo', 0) or 0),
                'map_name': match.get('map_name', ''),
                'date': int(match.get('date', 0) or 0),
                'party_size': 1,
                'result': int(match.get('result', 0) or 0),
                'my_faction': '',
                'my_stats': me_fallback,
                'teammates': [],
                'enemies': [],
            }, 'only_self')

        my_faction = None
        my_stats = None
        for p in players:
            if p.get('player_id') == my_player_id:
                my_faction = p.get('faction')
                my_stats = p
                break
        if not my_faction:
            return (None, 'no_my_faction')
        teammates = [p for p in players
                     if p.get('faction') == my_faction
                     and p.get('player_id') != my_player_id]
        enemies = [p for p in players if p.get('faction') != my_faction]
        return ({
            'match_id': mid,
            'elo': int(match.get('elo', 0) or 0),
            'map_name': match.get('map_name', ''),
            'date': int(match.get('date', 0) or 0),
            'party_size': len(teammates) + 1,
            'result': int(match.get('result', 0) or 0),
            'my_faction': my_faction,
            'my_stats': my_stats,
            'teammates': teammates,
            'enemies': enemies,
        }, None)

    async def collect_matches(self, matches, my_player_id, limit=50,
                              enrich_countries=True, enrich_elo=True):
        subset = matches[:limit]
        total = len(subset)
        if not total:
            return []
        logger.info(f'collect_matches: {total} матчей, '
                    f'{self.max_workers} потоков')

        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers)
        results = []
        done = 0
        reasons = {}
        try:
            tasks = [
                loop.run_in_executor(executor, self._collect_one,
                                      m, my_player_id)
                for m in subset
            ]
            for coro in asyncio.as_completed(tasks):
                done += 1
                try:
                    r, reason = await coro
                except Exception as e:
                    logger.debug(f'  collect err: {e}')
                    r, reason = (None, 'exc')
                if r:
                    results.append(r)
                    # ★ стриминг: сразу отдаём матч наружу
                    if self.on_match_collected:
                        try:
                            self.on_match_collected(r)
                        except Exception as e:
                            logger.debug(f'  on_match_collected err: {e}')
                else:
                    reasons[reason] = reasons.get(reason, 0) + 1
                if self.on_progress and (done % 5 == 0 or done == total):
                    self.on_progress(done, total, f'{done}/{total}')
        finally:
            executor.shutdown(wait=False)

        only_self = reasons.pop('only_self', 0)
        logger.info(f'  собрано: {len(results)}/{total} '
                    f'(из них без деталей: {only_self})')
        if reasons:
            reasons_str = ', '.join(f'{k}={v}' for k, v in reasons.items())
            logger.info(f'  ⚠ пропущено {sum(reasons.values())} ({reasons_str})')
        if not results:
            return []

        # ── Страны ──
        if enrich_countries:
            try:
                from src.services.country_resolver import get_resolver
                resolver = get_resolver()
                nicks = set()
                for entry in results:
                    for p in entry['teammates'] + entry['enemies']:
                        n = p.get('nickname', '')
                        if n and not p.get('country'):
                            nicks.add(n)
                logger.info(f'  countries: {len(nicks)} ников')
                for n in nicks:
                    resolver.get_country(n)
                for entry in results:
                    for p in entry['teammates'] + entry['enemies']:
                        n = (p.get('nickname') or '').lower()
                        if not p.get('country'):
                            p['country'] = resolver._cache.get(n, '')
            except Exception as e:
                logger.error(f'countries err: {e}')

        # ── ELO ──
        if enrich_elo:
            try:
                from src.services.player_elo_resolver import get_elo_resolver
                resolver = get_elo_resolver()
                all_players = []
                for entry in results:
                    if entry.get('my_stats'):
                        all_players.append(entry['my_stats'])
                    for p in entry['teammates'] + entry['enemies']:
                        all_players.append(p)
                seen = set()
                unique = []
                for p in all_players:
                    k = (p.get('player_id') or p.get('nickname') or '').lower()
                    if k and k not in seen:
                        seen.add(k)
                        unique.append(p)
                logger.info(f'  ELO: {len(unique)} уникальных игроков')
                elo_map = resolver.batch_get_players(unique, max_workers=16)
                ok = 0

                def _apply(p):
                    nonlocal ok
                    k1 = (p.get('player_id') or '').lower()
                    k2 = (p.get('nickname') or '').lower()
                    info = elo_map.get(k1) or elo_map.get(k2) or {}
                    if info.get('elo'):
                        p['player_elo'] = info.get('elo', 0)
                        p['player_level'] = info.get('level', 0)
                        p['player_winrate'] = info.get('winrate', 0)
                        ok += 1
                    else:
                        p.setdefault('player_elo', 0)

                for entry in results:
                    if entry.get('my_stats'):
                        _apply(entry['my_stats'])
                    for p in entry['teammates'] + entry['enemies']:
                        _apply(p)
                logger.info(f'  ELO получено: {ok}')
            except Exception as e:
                import traceback
                logger.error(f'elo err: {e}\n{traceback.format_exc()}')

        return results

    def detect_friends(self, match_data, min_appearances=2):
        c = Counter()
        for entry in match_data:
            for p in entry['teammates']:
                key = p.get('player_id') or p.get('nickname', '')
                if key:
                    c[key] += 1
        return {k for k, n in c.items() if n >= min_appearances}

    def build_stats_by_elo(self, match_data, elo_step=None, filter_party=None,
                           friends_set=None, filter_countries=None,
                           median_mode=False, elo_mode='personal'):
        step = elo_step or self.elo_step
        if friends_set is None:
            friends_set = self.detect_friends(match_data)
        if filter_countries is None:
            fc = None
        else:
            fc = {c.lower() for c in filter_countries}
            if not fc:
                return ({}, {}, {}, {})

        tm_items = defaultdict(list)
        en_items = defaultdict(list)
        fr_items = defaultdict(list)
        pl_items = defaultdict(list)

        for entry in match_data:
            match_elo = int(entry.get('elo', 0) or 0)
            if filter_party and entry.get('party_size') not in filter_party:
                continue
            won = 1 if entry.get('result') == 1 else 0

            def bucket_for(p):
                if elo_mode == 'personal':
                    pe = int(p.get('player_elo', 0) or 0)
                    base = pe if pe > 0 else match_elo
                else:
                    base = match_elo
                if not base:
                    return None
                return base // step * step

            for p in entry['teammates']:
                if fc is not None and (p.get('country') or '').lower() not in fc:
                    continue
                b = bucket_for(p)
                if b is None:
                    continue
                tm_items[b].append((p, won))
                key = p.get('player_id') or p.get('nickname', '')
                if key in friends_set:
                    fr_items[b].append((p, won))

            for p in entry['enemies']:
                if fc is not None and (p.get('country') or '').lower() not in fc:
                    continue
                b = bucket_for(p)
                if b is None:
                    continue
                en_items[b].append((p, won))

            if entry.get('my_stats'):
                me = entry['my_stats']
                if fc is not None and (me.get('country') or '').lower() not in fc:
                    continue
                if elo_mode == 'personal':
                    pe = int(entry.get('elo', 0) or 0)
                    if not pe:
                        pe = int(me.get('player_elo', 0) or 0)
                else:
                    pe = int(entry.get('elo', 0) or 0)
                if pe:
                    pl_items[pe // step * step].append((me, won))

        def _s(vals):
            if not vals:
                return 0
            if median_mode:
                return round(statistics.median(vals), 2)
            return round(sum(vals) / len(vals), 2)

        def _stat(vals):
            if not vals:
                return {'min': 0, 'max': 0, 'avg': 0, 'med': 0}
            return {'min': round(min(vals), 2), 'max': round(max(vals), 2),
                    'avg': round(sum(vals) / len(vals), 2),
                    'med': round(statistics.median(vals), 2)}

        def agg(items):
            if not items:
                return None
            players = [p for p, _ in items]
            wr_values = []
            for p, w in items:
                pw = p.get('player_winrate', 0)
                wr_values.append(float(pw) if pw else w * 100)
            kd = [float(p.get('kd_ratio', 0) or 0) for p in players if p.get('kd_ratio')]
            kr = [float(p.get('kr_ratio', 0) or 0) for p in players if p.get('kr_ratio')]
            adr = [float(p.get('adr', 0) or 0) for p in players if p.get('adr')]
            hs = [float(p.get('headshots_percent', 0) or 0) for p in players if p.get('headshots_percent')]
            rating = [float(p.get('rating', 0) or 0) for p in players if p.get('rating')]
            return {
                'count': len(players), 'matches': len(items),
                'wr': round(_s(wr_values), 1),
                'kd': _s(kd), 'kr': _s(kr), 'adr': _s(adr), 'hs': _s(hs),
                'kills': _s([p.get('kills', 0) for p in players]),
                'deaths': _s([p.get('deaths', 0) for p in players]),
                'assists': _s([p.get('assists', 0) for p in players]),
                'rating': _s(rating),
                'swing': _s([p.get('swing', 0) for p in players if p.get('swing')]),
                'matches_avg': _s([0]),
                'kd_min': min(kd) if kd else 0, 'kd_max': max(kd) if kd else 0,
                'adr_min': min(adr) if adr else 0, 'adr_max': max(adr) if adr else 0,
                '_stats': {'kd': _stat(kd), 'adr': _stat(adr), 'hs': _stat(hs),
                           'kr': _stat(kr), 'rating': _stat(rating)},
            }

        tm = {b: agg(tm_items[b]) for b in tm_items}
        en = {b: agg(en_items[b]) for b in en_items}
        pl = {b: agg(pl_items[b]) for b in pl_items}
        fr = {b: agg(fr_items[b]) for b in fr_items}
        return (tm, en, pl, fr)

    def extract_countries(self, match_data):
        c = set()
        for entry in match_data:
            for p in entry['teammates'] + entry['enemies']:
                cc = p.get('country', '')
                if cc:
                    c.add(cc.lower())
        return sorted(c)

    def collect_all_elos(self, match_data):
        elos = []
        for entry in match_data:
            for p in entry['teammates'] + entry['enemies']:
                pe = int(p.get('player_elo', 0) or 0)
                if pe > 0:
                    elos.append(pe)
        return elos

    def build_deep_conclusions(self, match_data, friends_set):
        try:
            from src.core.analytics.conclusions import DeepConclusions
            return DeepConclusions(friends_set).analyze(match_data)
        except Exception as e:
            logger.error(f'conclusions err: {e}')
            return {}
