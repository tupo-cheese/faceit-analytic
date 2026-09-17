import time
import random
import logging
from curl_cffi import requests as cffi_requests
from src.data_sources.base import DataSource
from src.config import SETTINGS
from src.services.proxy_rotator import get_proxy_rotator

logger = logging.getLogger('faceit_analytics')


class FaceitSource(DataSource):
    name = 'faceit'
    CORE = 'https://api.faceit.com/core/v1'
    STATS = 'https://api.faceit.com/stats/v1'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://www.faceit.com/',
        'Origin': 'https://www.faceit.com',
    }
    UA_LIST = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/17.0',
    ]
    LANG_MAP = {'ru': 'ru', 'uk': 'ru', 'kz': 'ru', 'by': 'ru', 'de': 'de',
                'fr': 'fr', 'es': 'es', 'it': 'it', 'pt': 'pt', 'tr': 'tr',
                'pl': 'pl', 'en': 'en'}

    def __init__(self, cache, api_key=''):
        self.cache = cache
        self.api_key = api_key or SETTINGS.faceit_api_key
        self.proxy = get_proxy_rotator()

    def _headers(self):
        h = dict(self.HEADERS)
        h['User-Agent'] = random.choice(self.UA_LIST)
        return h

    def _try_request(self, url, params, proxy, profile='chrome120', timeout=8):
        """Одна попытка. Возвращает (status_code, json_or_None)."""
        try:
            r = cffi_requests.get(url, params=params, headers=self._headers(),
                                   impersonate=profile, timeout=timeout,
                                   proxies=proxy)
            if r.status_code == 200:
                try:
                    return (200, r.json())
                except Exception:
                    return (200, None)
            return (r.status_code, None)
        except Exception:
            return (None, None)

    def _get_json(self, url, params=None, max_attempts=10):
        for attempt in range(max_attempts):
            proxy = self.proxy.get()
            for profile in ['chrome120', 'safari184']:
                status, data = self._try_request(url, params, proxy, profile)
                if status == 200 and data is not None:
                    self.proxy.report_ok(proxy)
                    logger.info(f'  [http] OK через {"прокси" if proxy else "прямой IP"} '
                                f'(попытка {attempt + 1})')
                    return data
                if status == 429:
                    self.proxy.report_fail(proxy)
                    break
                if status in (401, 403):
                    break
        # fallback: прямой запрос (может, бан снят)
        logger.info('  [http] все прокси исчерпаны, пробую прямой IP')
        status, data = self._try_request(url, params, None, 'chrome120', timeout=10)
        if status == 200 and data is not None:
            logger.info('  [http] ✅ прямой IP сработал!')
            return data
        return None

    def _get_html(self, url):
        for attempt in range(6):
            proxy = self.proxy.get()
            try:
                r = cffi_requests.get(url, headers=self._headers(),
                                       impersonate='chrome124', timeout=8,
                                       proxies=proxy)
                if r.status_code == 200 and len(r.text) > 1000:
                    return r.text
                if r.status_code == 429:
                    self.proxy.report_fail(proxy)
            except Exception:
                self.proxy.report_fail(proxy)
        try:
            r = cffi_requests.get(url, headers=self._headers(),
                                   impersonate='chrome124', timeout=10)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
        except Exception:
            pass
        return None

    async def fetch_player(self, steam_id):
        cached = self.cache.get('faceit_player', steam_id)
        if cached:
            return cached
        base = {}
        steamgpt_data = None
        for attempt in range(4):
            try:
                proxy = self.proxy.get()
                r = cffi_requests.get(f'https://steamgpt.net/faceit/{steam_id}.json',
                                       impersonate='chrome124', timeout=10,
                                       proxies=proxy)
                if r.status_code == 200:
                    self.proxy.report_ok(proxy)
                    steamgpt_data = r.json()
                    break
            except Exception as e:
                logger.debug(f'  [faceit] steamgpt attempt {attempt+1} err: {e}')
                self.proxy.report_fail(proxy)
        if steamgpt_data is not None:
            try:
                data = steamgpt_data
                if data.get('result') == 'success':
                    faceit = data.get('data', {}).get('faceit', {})
                    nick = faceit.get('nickname', '')
                    country = (faceit.get('country', '') or '').lower()
                    games = faceit.get('games', {}) or {}
                    cs2 = games.get('cs2') or games.get('CS2') or {}
                    lang = self.LANG_MAP.get(country, 'en')
                    base = {
                        'steam_id': steam_id,
                        'faceit_id': faceit.get('player_id', ''),
                        'nickname': nick,
                        'avatar_url': faceit.get('avatar', ''),
                        'country': country,
                        'faceit_url': f'https://www.faceit.com/{lang}/players/{nick}',
                        'faceit_level': cs2.get('skill_level', 0),
                        'faceit_elo': cs2.get('faceit_elo', 0),
                        'faceit_region': cs2.get('region', ''),
                        'faceit_banned': bool(faceit.get('bans')),
                    }
            except Exception as e:
                logger.warning(f'  [faceit] parse err: {e}')
        pid = base.get('faceit_id', '')
        if pid:
            stats = self._get_json(f'{self.CORE}/players/{pid}/stats/cs2')
            if stats and 'lifetime' in stats:
                lt = stats['lifetime']
                base['matches_total'] = lt.get('Matches', '—')
                base['win_rate'] = lt.get('Win Rate %', '—')
                base['avg_kd'] = lt.get('Average K/D Ratio', '—')
                base['avg_hs'] = lt.get('Average Headshots %', '—')
                base['recent_results'] = lt.get('Recent Results', [])
                base['current_win_streak'] = lt.get('Current Win Streak', 0)
                base['longest_win_streak'] = lt.get('Longest Win Streak', '—')
        if base.get('faceit_id'):
            self.cache.set('faceit_player', steam_id, base)
        return base

    def _parse_match(self, m):
        def to_int(v):
            try:
                return int(v)
            except Exception:
                return 0

        def to_float(v):
            try:
                return float(v)
            except Exception:
                return 0.0

        def to_str(v):
            return str(v) if v is not None else ''

        mid = m.get('matchId') or m.get('match_id') or ''
        kills = to_int(m.get('i6', 0))
        deaths = to_int(m.get('i8', 0))
        assists = to_int(m.get('i7', 0))
        rounds = to_int(m.get('i12', 0))
        result_raw = to_int(m.get('i10', 0))
        score_raw = to_str(m.get('i18', ''))
        score_a, score_b = 0, 0
        if ' / ' in score_raw:
            parts = score_raw.split(' / ')
            try:
                score_a, score_b = int(parts[0]), int(parts[1])
            except Exception:
                pass
        entry = {
            'match_id': mid, 'id': mid, 'source': 'faceit',
            'game': m.get('game', 'cs2'),
            'date': to_int(m.get('date', 0)),
            'created_at': to_int(m.get('created_at', 0)),
            'elo': to_int(m.get('elo', 0)),
            'elo_delta': to_int(m.get('elo_delta', 0)),
            'region': to_str(m.get('i0', '')),
            'map_name': to_str(m.get('i1', '')),
            'result': result_raw,
            'score_a': score_a, 'score_b': score_b, 'score_raw': score_raw,
            'kills': kills, 'deaths': deaths, 'assists': assists, 'rounds': rounds,
            'mvps': to_int(m.get('i9', 0)),
            'triple_kills': to_int(m.get('i14', 0)),
            'quadro_kills': to_int(m.get('i15', 0)),
            'penta_kills': to_int(m.get('i16', 0)),
            'total_damage': to_int(m.get('i20', 0)),
            'headshots_percent': to_float(m.get('c4', 0)),
            'kd_ratio': to_float(m.get('c2', 0)),
            'kr_ratio': to_float(m.get('c3', 0)),
            'adr': to_float(m.get('c10', 0)),
            'nickname': to_str(m.get('nickname', '')),
            'playerId': to_str(m.get('playerId', '')),
            'premade': bool(m.get('premade', False)),
        }
        if entry['kd_ratio'] == 0.0 and deaths:
            entry['kd_ratio'] = round(kills / deaths, 2)
        return entry

    async def fetch_matches(self, steam_id, limit=100):
        cached = self.cache.get('faceit_matches', steam_id)
        if cached and len(cached) >= min(limit, 100):
            logger.info(f'  [matches] из кэша: {len(cached)}')
            return cached[:limit]
        player = await self.fetch_player(steam_id)
        if not player or not player.get('faceit_id'):
            logger.warning('  [matches] нет faceit_id')
            return []
        pid = player['faceit_id']
        limit = min(limit, 100)
        url = f'{self.STATS}/stats/time/users/{pid}/games/cs2'
        logger.info(f'  [matches] stats API: {limit} матчей '
                    f'(прокси: {self.proxy.count}/{self.proxy.total})')
        data = self._get_json(url, params={'size': limit, 'page': 0},
                              max_attempts=10)
        if isinstance(data, dict):
            data = data.get('items', data.get('data', []))
        matches = []
        if isinstance(data, list):
            for m in data[:limit]:
                entry = self._parse_match(m)
                if entry.get('match_id'):
                    matches.append(entry)
            logger.info(f'  [matches] распарсено: {len(matches)}')
        else:
            logger.warning('  [matches] не удалось получить ни одного матча')
        if matches:
            self.cache.set('faceit_matches', steam_id, matches)
        return matches

    async def fetch_matches_more(self, steam_id, page=1, size=100):
        """Загружает дополнительные матчи (страница N)."""
        player = await self.fetch_player(steam_id)
        if not player or not player.get('faceit_id'):
            return []
        pid = player['faceit_id']
        url = f'{self.STATS}/stats/time/users/{pid}/games/cs2'
        logger.info(f'  [matches-more] page={page} size={size}')
        data = self._get_json(url, params={'size': min(size, 100), 'page': page},
                              max_attempts=10)
        if isinstance(data, dict):
            data = data.get('items', data.get('data', []))
        if not isinstance(data, list):
            return []
        matches = []
        for m in data:
            e = self._parse_match(m)
            if e.get('match_id'):
                matches.append(e)
        logger.info(f'  [matches-more] +{len(matches)}')
        # merge with existing cache
        existing = self.cache.get('faceit_matches', steam_id) or []
        seen = {m['match_id'] for m in existing}
        merged = list(existing)
        added = 0
        for m in matches:
            if m['match_id'] not in seen:
                merged.append(m)
                seen.add(m['match_id'])
                added += 1
        self.cache.set('faceit_matches', steam_id, merged)
        logger.info(f'  [matches-more] итого: {len(merged)} (+{added})')
        return merged

    async def close(self):
        pass
