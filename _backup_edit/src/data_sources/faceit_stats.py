import time
import logging
import concurrent.futures
from curl_cffi import requests as cffi_requests
from src.services.proxy_rotator import get_proxy_rotator

logger = logging.getLogger('faceit_analytics')


class FaceitMatchStats:
    BASE = 'https://api.faceit.com/stats/v1/stats'
    V2 = 'https://api.faceit.com/match/v2/match'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.faceit.com/',
        'Origin': 'https://www.faceit.com',
    }

    @classmethod
    def _get_country(cls, nickname):
        try:
            from src.services.country_resolver import get_resolver
            return get_resolver().get_country(nickname)
        except Exception:
            return ''

    @classmethod
    def _try_one(cls, url, proxy, timeout=6):
        try:
            r = cffi_requests.get(url, headers=cls.HEADERS,
                                   impersonate='safari184', timeout=timeout,
                                   proxies=proxy)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    @classmethod
    def fetch_raw(cls, match_id):
        rotator = get_proxy_rotator()
        urls = [f'{cls.BASE}/matches/{match_id}',
                f'{cls.V2}/{match_id}']
        # 3 параллельные попытки — гонка: первый успех выигрывает
        for round_idx in range(2):
            attempts = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
                for url in urls:
                    for _ in range(2):
                        proxy = rotator.get()
                        attempts.append((url, proxy,
                                          ex.submit(cls._try_one, url, proxy)))
                done, pending = concurrent.futures.wait(
                    [a[2] for a in attempts], timeout=8,
                    return_when=concurrent.futures.FIRST_COMPLETED)
                for f in done:
                    try:
                        data = f.result()
                        if data:
                            # угадать какой был прокси — по индексу
                            idx = [a[2] for a in attempts].index(f)
                            rotator.report_ok(attempts[idx][1])
                            for a in attempts:
                                a[2].cancel()
                            if isinstance(data, dict) and 'payload' in data:
                                return data['payload']
                            return data
                    except Exception:
                        pass
                for f in pending:
                    f.cancel()
                for a in attempts:
                    if not a[2].done():
                        rotator.report_fail(a[1])
        return None

    @classmethod
    def fetch_match(cls, match_id, with_country=True):
        data = cls.fetch_raw(match_id)
        players = cls._extract_players(data) if data else []
        if players and with_country:
            for p in players:
                nick = p.get('nickname', '')
                if nick and not p.get('country'):
                    p['country'] = cls._get_country(nick)
        return players

    @classmethod
    def _extract_players(cls, data):
        if not data:
            return []
        players = []
        item = None
        if isinstance(data, list):
            if not data:
                return []
            item = data[0]
        elif isinstance(data, dict):
            item = data
        if not isinstance(item, dict):
            return []
        teams = item.get('teams')
        if isinstance(teams, list):
            for team in teams:
                faction = team.get('teamId', team.get('faction', ''))
                for p in team.get('players', []) or []:
                    players.append(cls._map_player(p, faction))
        elif isinstance(teams, dict):
            for faction, team in teams.items():
                if isinstance(team, dict):
                    for p in team.get('players', []) or []:
                        players.append(cls._map_player(p, faction))
        seen = set()
        unique = []
        for p in players:
            k = p.get('player_id') or p.get('nickname')
            if k and k not in seen:
                seen.add(k)
                unique.append(p)
        return unique

    @staticmethod
    def _map_player(p, faction=''):
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

        pid = p.get('player_id') or p.get('playerId') or ''
        nick = p.get('nickname', '') or ''
        kills = to_int(p.get('i6', 0)) or to_int(p.get('kills', 0))
        deaths = to_int(p.get('i8', 0)) or to_int(p.get('deaths', 0))
        assists = to_int(p.get('i7', 0)) or to_int(p.get('assists', 0))
        kd = to_float(p.get('c2', 0))
        kr = to_float(p.get('c3', 0))
        hs_pct = to_float(p.get('c4', 0))
        adr = to_float(p.get('c10', 0))
        mvps = to_int(p.get('i9', 0))
        headshots = to_int(p.get('i13', 0))
        triple = to_int(p.get('i14', 0))
        quadro = to_int(p.get('i15', 0))
        penta = to_int(p.get('i16', 0))
        rounds = to_int(p.get('i28', 0))
        result = to_int(p.get('i10', 0))
        if not kd and deaths:
            kd = round(kills / deaths, 2)
        kast_est = 60 + min(mvps * 3, 12) + min((triple + quadro + penta) * 2, 8)
        kast_est = min(80, max(55, kast_est))
        rating = 0.0073 * kast_est + 0.3591 * kd + 0.5329 * kr
        rating = round(max(0.3, min(1.8, rating)), 2)
        swing = round((rating - 1.0) * 100, 2) if rating else 0.0
        return {
            'player_id': pid, 'nickname': nick, 'avatar': p.get('avatar', ''),
            'faction': faction, 'country': p.get('country', ''),
            'kills': kills, 'deaths': deaths, 'assists': assists,
            'kd_ratio': kd, 'kr_ratio': kr, 'adr': adr,
            'headshots': headshots, 'headshots_percent': hs_pct,
            'mvps': mvps, 'triple_kills': triple, 'quadro_kills': quadro,
            'penta_kills': penta, 'rounds': rounds,
            'rating': rating, 'swing': swing, 'result': result,
        }
