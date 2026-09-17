import re
import logging
from pathlib import Path
from curl_cffi import requests as cffi_requests
from src.data_sources.base import DataSource
from src.services.proxy_rotator import get_proxy_rotator

logger = logging.getLogger('faceit_analytics')


class CSStatsSource(DataSource):
    name = 'csstats'
    BASE = 'https://csstats.gg'
    HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    def __init__(self, cache):
        self.cache = cache
        self.proxy = get_proxy_rotator()

    def _get_html(self, url):
        for attempt in range(6):
            proxy = self.proxy.get()
            for profile in ['safari184', 'chrome124']:
                try:
                    r = cffi_requests.get(url, impersonate=profile,
                                           timeout=15, headers=self.HEADERS,
                                           proxies=proxy)
                    if r.status_code == 200 and 'Just a moment' not in r.text[:500]:
                        self.proxy.report_ok(proxy)
                        return r.text
                    if r.status_code == 429:
                        self.proxy.report_fail(proxy)
                        break
                except Exception:
                    self.proxy.report_fail(proxy)
        # fallback без прокси
        try:
            r = cffi_requests.get(url, impersonate='safari184', timeout=15,
                                   headers=self.HEADERS)
            if r.status_code == 200 and 'Just a moment' not in r.text[:500]:
                return r.text
        except Exception:
            pass
        return None

    def _parse_pm(self, html):
        stats = {}
        for m in re.finditer(
                r'<div class="pm-c">\s*<span class="k">([^<]+)</span>\s*<span class="v">(.*?)</span>\s*</div>',
                html, re.S):
            key = m.group(1).strip()
            val = re.sub(r'<[^>]+>', ' ', m.group(2))
            val = re.sub(r'\s+', ' ', val).strip()
            num = re.search(r'-?\d+\.?\d*', val)
            stats[key] = num.group(0) if num else val
        return stats

    async def fetch_player(self, steam_id):
        cached = self.cache.get('csstats_player', steam_id)
        if cached:
            return cached
        html = self._get_html(f'{self.BASE}/player/{steam_id}')
        if not html:
            logger.info('  [csstats] не удалось получить HTML')
            return {'steam_id': steam_id, 'source': 'csstats',
                    'requires_auth': True}
        result = {'steam_id': steam_id, 'source': 'csstats',
                  'raw_html_len': len(html)}
        result['cards'] = self._parse_pm(html)

        patterns = {
            'kd': r'K/D(?:\s*Ratio)?[^0-9\-]{0,20}([\d.]+)',
            'adr': r'ADR[^0-9\-]{0,20}([\d.]+)',
            'hs': r'HS%[^0-9\-]{0,20}([\d.]+)',
            'rating': r'Rating[^0-9\-]{0,20}([\d.]+)',
            'kills_total': r'Kills[^0-9\-]{0,20}(\d+)',
            'deaths_total': r'Deaths[^0-9\-]{0,20}(\d+)',
            'matches_total': r'Matches[^0-9\-]{0,20}(\d+)',
            'wins': r'Wins[^0-9\-]{0,20}(\d+)',
            'kills_round': r'K/R Ratio[^0-9\-]{0,20}([\d.]+)',
            'headshots_total': r'Headshots[^0-9\-]{0,20}(\d+)',
            'mvps_total': r'MVPs?[^0-9\-]{0,20}(\d+)',
            'triple_kills': r'Triple Kills[^0-9\-]{0,20}(\d+)',
            'quadro_kills': r'Quadro Kills[^0-9\-]{0,20}(\d+)',
            'penta_kills': r'Penta Kills[^0-9\-]{0,20}(\d+)',
            'first_kills': r'First Kills?[^0-9\-]{0,20}(\d+)',
            'clutches_won': r'Clutches Won[^0-9\-]{0,20}(\d+)',
            'longest_win_streak': r'Longest Win Streak[^0-9\-]{0,20}(\d+)',
            'rounds_total': r'Rounds[^0-9\-]{0,20}(\d+)',
        }
        for key, pat in patterns.items():
            m = re.search(pat, html, re.I)
            if m:
                result[key] = m.group(1)
        m = re.search(r'cs2rating[^"]*"[^>]*style="[^"]*rating\.(\w+)', html)
        if m:
            result['rating_badge'] = m.group(1)
        # win_rate
        if result.get('wins') and result.get('matches_total'):
            try:
                result['win_rate'] = round(
                    int(result['wins']) / int(result['matches_total']) * 100, 1)
            except Exception:
                pass
        try:
            from src.config import DATA_DIR
            (DATA_DIR / 'debug' / f'csstats_{steam_id}.html').write_text(
                html, encoding='utf-8')
        except Exception:
            pass
        self.cache.set('csstats_player', steam_id, result)
        return result

    async def fetch_matches(self, steam_id, limit=50):
        return []

    async def close(self):
        pass
