import re
import logging
from curl_cffi import requests as cffi_requests
from src.data_sources.base import DataSource
from src.services.proxy_rotator import get_proxy_rotator

logger = logging.getLogger('faceit_analytics')


class FaceitAnalyserSource(DataSource):
    name = 'faceitanalyser'
    BASE = 'https://faceitanalyser.com/api'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/json,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://faceitanalyser.com/',
    }

    def __init__(self, cache, api_key=''):
        self.cache = cache
        self.api_key = api_key
        self.proxy = get_proxy_rotator()

    def _get_html(self, url):
        for attempt in range(6):
            proxy = self.proxy.get()
            try:
                r = cffi_requests.get(url, headers=self.HEADERS,
                                       impersonate='chrome120', timeout=10,
                                       proxies=proxy)
                if r.status_code == 200 and len(r.text) > 1000:
                    return r.text
            except Exception:
                self.proxy.report_fail(proxy)
        try:
            r = cffi_requests.get(url, headers=self.HEADERS,
                                   impersonate='chrome120', timeout=10)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
        except Exception:
            pass
        return None

    async def fetch_player(self, steam_id, nickname=''):
        cached = self.cache.get('fa_player', steam_id)
        if cached:
            return cached
        if not nickname:
            try:
                proxy = self.proxy.get()
                r = cffi_requests.get(f'https://steamgpt.net/faceit/{steam_id}.json',
                                       impersonate='chrome124', timeout=15,
                                       proxies=proxy)
                if r.status_code == 200:
                    nickname = r.json().get('data', {}).get('faceit', {}).get('nickname', '')
            except Exception:
                pass
        if not nickname:
            return None
        html = self._get_html(f'https://faceitanalyser.com/player/{nickname}')
        if not html:
            return None
        result = {'steam_id': steam_id, 'source': 'faceitanalyser',
                  'nickname': nickname, 'raw_html_len': len(html)}
        for key, pats in [
            ('kd', [r'K/D[^0-9\-]{0,20}([\d.]+)']),
            ('adr', [r'ADR[^0-9\-]{0,20}([\d.]+)']),
            ('hs', [r'HS%[^0-9\-]{0,20}([\d.]+)']),
            ('kr', [r'K/R[^0-9\-]{0,20}([\d.]+)']),
            ('rating', [r'Rating[^0-9\-]{0,20}([\d.]+)']),
            ('entry_rate', [r'Entry[^0-9\-]{0,20}([\d.]+)%']),
            ('clutch_rate', [r'Clutch[^0-9\-]{0,20}([\d.]+)%']),
            ('utility_usage', [r'Utility[^0-9\-]{0,20}([\d.]+)']),
            ('flash_success', [r'Flash[^0-9\-]{0,20}([\d.]+)%']),
            ('sniper_kills', [r'AWP[^0-9\-]{0,20}([\d.]+)']),
            ('mvps', [r'MVPs?[^0-9\-]{0,20}([\d.]+)']),
        ]:
            for pat in pats:
                m = re.search(pat, html, re.I)
                if m:
                    result[key] = m.group(1)
                    break
        try:
            from src.config import DATA_DIR
            (DATA_DIR / 'debug' / f'fa_html_{steam_id}.html').write_text(
                html, encoding='utf-8')
        except Exception:
            pass
        self.cache.set('fa_player', steam_id, result)
        return result

    async def fetch_matches(self, steam_id, limit=30, nickname=''):
        return []

    async def close(self):
        pass
