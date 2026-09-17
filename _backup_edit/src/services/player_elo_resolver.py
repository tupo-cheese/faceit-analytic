import json
import re
import time
import logging
import concurrent.futures
from curl_cffi import requests as cffi_requests
from src.services.proxy_rotator import get_proxy_rotator

logger = logging.getLogger('faceit_analytics')


class PlayerEloResolver:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'application/json, text/html, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://www.faceit.com/',
        'Origin': 'https://www.faceit.com',
    }

    def __init__(self):
        self._cache = {}
        from src.config import DATA_DIR
        self._cache_file = DATA_DIR / 'player_elo_cache.json'
        self._debug_dir = DATA_DIR / 'debug'
        self._debug_dir.mkdir(parents=True, exist_ok=True)
        self.proxy = get_proxy_rotator()
        self._load()

    def _load(self):
        if self._cache_file.exists():
            try:
                self._cache = json.loads(self._cache_file.read_text(encoding='utf-8'))
                logger.info(f'ELO cache: {len(self._cache)} записей')
            except Exception:
                pass

    def _save(self):
        try:
            self._cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding='utf-8')
        except Exception:
            pass

    def _parse_json(self, data):
        if not isinstance(data, dict):
            return {}

        def walk(obj, depth=0):
            if depth > 10:
                return None
            if isinstance(obj, dict):
                if obj.get('faceit_elo'):
                    return obj
                for v in obj.values():
                    r = walk(v, depth + 1)
                    if r:
                        return r
            elif isinstance(obj, list):
                for item in obj[:5]:
                    r = walk(item, depth + 1)
                    if r:
                        return r
            return None

        target = walk(data)
        if target:
            return {
                'elo': int(target.get('faceit_elo', 0) or 0),
                'level': int(target.get('skill_level', 0) or 0),
                'winrate': float(target.get('win_rate', 0)
                                 or target.get('winRate', 0) or 0),
            }
        return {}

    def _try_endpoint(self, url, is_json=True, timeout=5):
        for prof in ['safari184', 'chrome120']:
            proxy = self.proxy.get()
            try:
                r = cffi_requests.get(url, headers=self.HEADERS,
                                       impersonate=prof, timeout=timeout,
                                       proxies=proxy)
                if r.status_code != 200:
                    if r.status_code == 429:
                        self.proxy.report_fail(proxy)
                    continue
                self.proxy.report_ok(proxy)
                if is_json:
                    try:
                        result = self._parse_json(r.json())
                        if result.get('elo'):
                            return (result, r.text)
                    except Exception:
                        pass
                else:
                    return (None, r.text)
            except Exception:
                self.proxy.report_fail(proxy)
                continue
        return (None, None)

    def _fetch_by_player_id(self, player_id):
        if not player_id:
            return ({}, None)
        for url in [f'https://api.faceit.com/core/v1/players/{player_id}',
                    f'https://api.faceit.com/users/v1/users/{player_id}']:
            result, raw = self._try_endpoint(url, is_json=True, timeout=5)
            if result and result.get('elo'):
                return (result, raw)
        return ({}, None)

    def _fetch_html(self, nickname):
        if not nickname:
            return ({}, None)
        import urllib.parse
        nick_q = urllib.parse.quote(nickname.replace(' ', '%20'))
        for url in [f'https://www.faceit.com/ru/players/{nick_q}']:
            _, raw = self._try_endpoint(url, is_json=False, timeout=6)
            if not raw:
                continue
            result = {}
            m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                          raw, re.S)
            if m:
                try:
                    result = self._parse_json(json.loads(m.group(1)))
                except Exception:
                    pass
            if not result.get('elo'):
                m = re.search(r'"faceit_elo"\s*:\s*(\d+)', raw)
                if m:
                    result['elo'] = int(m.group(1))
            if not result.get('level'):
                m = re.search(r'"skill_level"\s*:\s*(\d+)', raw)
                if m:
                    result['level'] = int(m.group(1))
            if result.get('elo'):
                return (result, raw)
        return ({}, None)

    def _fetch_one(self, args):
        nickname, player_id = args
        key = (player_id or nickname or '').lower()
        if not key:
            return (key, {})
        data, _ = self._fetch_by_player_id(player_id)
        if not data.get('elo'):
            data2, _ = self._fetch_html(nickname)
            if data2.get('elo'):
                data = data2
        return (key, data)

    def batch_get_players(self, players, max_workers=8, batch_timeout=300):
        result = {}
        to_fetch = []
        for p in players:
            nickname = p.get('nickname', '')
            player_id = p.get('player_id', '')
            k = (player_id or nickname or '').lower()
            if not k:
                continue
            if k in self._cache and self._cache[k].get('elo'):
                result[k] = self._cache[k]
            else:
                to_fetch.append((nickname, player_id))
        if not to_fetch:
            logger.info(f'ELO: всё из кэша ({len(result)})')
            return result
        logger.info(f'ELO fetch: {len(to_fetch)} новых, {max_workers} потоков, '
                    f'прокси: {self.proxy.count}/{self.proxy.total}')
        ok = 0
        done = 0
        start = time.time()
        last_log = start
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        futures = {ex.submit(self._fetch_one, a): a for a in to_fetch}
        try:
            for f in concurrent.futures.as_completed(futures, timeout=batch_timeout):
                done += 1
                try:
                    key, data = f.result(timeout=0.1)
                except Exception:
                    continue
                if data and data.get('elo'):
                    self._cache[key] = data
                    result[key] = data
                    ok += 1
                now = time.time()
                if done % 10 == 0 or (now - last_log) > 20:
                    elapsed = now - start
                    rate = done / max(elapsed, 0.01)
                    eta = (len(to_fetch) - done) / max(rate, 0.01)
                    logger.info(f'  ELO: {done}/{len(to_fetch)} '
                                f'(ok={ok}, {rate:.1f}/s, ETA {eta:.0f}s)')
                    last_log = now
        except concurrent.futures.TimeoutError:
            logger.warning(f'  ELO: timeout {batch_timeout}s — '
                            f'{done}/{len(to_fetch)} (ok={ok})')
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        logger.info(f'  ✅ ELO: {ok}/{len(to_fetch)} за {time.time() - start:.0f}s')
        self._save()
        return result

    def batch_get(self, nicks, max_workers=8):
        players = [{'nickname': n} for n in nicks]
        return self.batch_get_players(players, max_workers)

    def _fetch_one_public(self, args):
        return self._fetch_one(args)


_resolver = None


def get_elo_resolver():
    global _resolver
    if _resolver is None:
        _resolver = PlayerEloResolver()
    return _resolver
