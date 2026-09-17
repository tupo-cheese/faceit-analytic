import re
import json
import logging
import concurrent.futures
from pathlib import Path

logger = logging.getLogger('faceit_analytics')


class MatchRoomParser:

    def __init__(self, html: str, match_id: str = ''):
        self.html = html
        self.match_id = match_id

    def extract_players(self):
        players = {}
        m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                      self.html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                self._walk(data, players)
            except Exception as e:
                logger.debug(f'  __NEXT_DATA__ err: {e}')
        for sm in re.finditer(
                r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                self.html, re.S):
            try:
                data = json.loads(sm.group(1))
                self._walk(data, players)
            except Exception:
                pass
        if len(players) < 5:
            self._regex_extract(players)
        seen = set()
        result = []
        for key, p in players.items():
            k = p.get('playerId') or p.get('nickname', '')
            if not k or k in seen:
                continue
            seen.add(k)
            result.append(p)
        return result

    def _walk(self, obj, players, depth=0):
        if depth > 15:
            return
        if isinstance(obj, dict):
            nick = obj.get('nickname')
            pid = obj.get('playerId') or obj.get('player_id')
            stats = obj.get('player_stats') or obj.get('stats') or {}
            if nick and (pid or stats):
                kills = self._int(stats.get('Kills', obj.get('kills', 0)))
                deaths = self._int(stats.get('Deaths', obj.get('deaths', 0)))
                assists = self._int(stats.get('Assists', obj.get('assists', 0)))
                kd = stats.get('K/D Ratio') or stats.get('kd_ratio')
                if not kd and deaths:
                    kd = round(kills / deaths, 2)
                hs = stats.get('Headshots %') or stats.get('headshots_percent')
                adr = stats.get('ADR') or stats.get('adr')
                mvps = self._int(stats.get('MVPs', obj.get('mvps', 0)))
                triple = self._int(stats.get('Triple Kills', 0))
                quadro = self._int(stats.get('Quadro Kills', 0))
                penta = self._int(stats.get('Penta Kills', 0))
                faction = obj.get('faction', '') or obj.get('team', '')
                players[pid or nick] = {
                    'nickname': nick, 'playerId': pid or '',
                    'player_id': pid or '',
                    'avatar': obj.get('avatar', ''),
                    'faction': faction,
                    'kills': kills, 'deaths': deaths, 'assists': assists,
                    'kd_ratio': float(kd) if kd else 0.0,
                    'headshots_percent': float(hs) if hs else 0.0,
                    'adr': float(adr) if adr else 0.0,
                    'mvps': mvps, 'triple_kills': triple,
                    'quadro_kills': quadro, 'penta_kills': penta,
                    'rating': 1.0,
                }
            for v in obj.values():
                self._walk(v, players, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:200]:
                self._walk(item, players, depth + 1)

    def _regex_extract(self, players):
        for m in re.finditer(
                r'"nickname"\s*:\s*"([^"]+)"[^}]*?"Kills"\s*:\s*"(\d+)"[^}]*?"Deaths"\s*:\s*"(\d+)"',
                self.html):
            nick = m.group(1)
            if nick in players:
                continue
            players[nick] = {
                'nickname': nick, 'playerId': '', 'player_id': '',
                'avatar': '', 'faction': '',
                'kills': int(m.group(2)), 'deaths': int(m.group(3)),
                'assists': 0,
                'kd_ratio': round(int(m.group(2)) / max(int(m.group(3)), 1), 2),
                'headshots_percent': 0.0, 'adr': 0.0,
                'mvps': 0, 'triple_kills': 0, 'quadro_kills': 0,
                'penta_kills': 0, 'rating': 1.0,
            }

    @staticmethod
    def _int(v):
        try:
            return int(v)
        except Exception:
            return 0


def _fetch_room_one(match_id, lang, proxy):
    from curl_cffi import requests as cffi
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://www.faceit.com/',
    }
    url = f'https://www.faceit.com/{lang}/cs2/room/{match_id}/scoreboard'
    try:
        r = cffi.get(url, impersonate='safari184', timeout=6,
                     headers=headers, proxies=proxy)
        if r.status_code == 200 and len(r.text) > 5000:
            parser = MatchRoomParser(r.text, match_id)
            players = parser.extract_players()
            if players:
                return players
    except Exception:
        pass
    return None


def fetch_room_players_sync(match_id: str) -> list:
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    # 4 параллельных попытки (ru/en × 2 прокси)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = []
        for lang in ('ru', 'en'):
            for _ in range(2):
                proxy = pr.get()
                futures.append((proxy, ex.submit(_fetch_room_one,
                                                  match_id, lang, proxy)))
        done, pending = concurrent.futures.wait(
            [f[1] for f in futures], timeout=10,
            return_when=concurrent.futures.FIRST_COMPLETED)
        for f in done:
            try:
                result = f.result()
                if result:
                    idx = [x[1] for x in futures].index(f)
                    pr.report_ok(futures[idx][0])
                    for x in futures:
                        x[1].cancel()
                    return result
            except Exception:
                pass
        for f in pending:
            f.cancel()
        for proxy, f in futures:
            if not f.done():
                pr.report_fail(proxy)
    return []


async def fetch_room_players(match_id: str) -> list:
    return fetch_room_players_sync(match_id)
