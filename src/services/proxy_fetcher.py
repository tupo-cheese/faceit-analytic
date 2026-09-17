import logging
from pathlib import Path

logger = logging.getLogger('faceit_analytics')


SOURCES = [
    ('proxyscrape_http',
     'https://api.proxyscrape.com/v4/free-proxy-list/get?'
     'request=display_proxies&protocol=http&proxy_format=protocolipport&format=text'),
    ('proxyscrape_socks5',
     'https://api.proxyscrape.com/v4/free-proxy-list/get?'
     'request=display_proxies&protocol=socks5&proxy_format=protocolipport&format=text'),
    ('proxy-list_download',
     'https://www.proxy-list.download/api/v1/get?type=http'),
    ('proxy-list_download_https',
     'https://www.proxy-list.download/api/v1/get?type=https'),
]


def fetch_proxies(limit_total=2000, append=False):
    """Скачивает свежие прокси из открытых источников."""
    from curl_cffi import requests as cffi
    from src.config import DATA_DIR
    proxies_file = DATA_DIR / 'proxies.txt'

    collected = set()
    for name, url in SOURCES:
        try:
            logger.info(f'  fetching {name}...')
            r = cffi.get(url, impersonate='chrome120', timeout=30)
            if r.status_code != 200:
                logger.warning(f'    HTTP {r.status_code}')
                continue
            added = 0
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '://' not in line:
                    # determine scheme
                    scheme = 'socks5' if 'socks5' in name else 'http'
                    line = f'{scheme}://{line}'
                collected.add(line)
                added += 1
                if len(collected) >= limit_total:
                    break
            logger.info(f'    +{added} (всего {len(collected)})')
        except Exception as e:
            logger.warning(f'    err: {e}')

    if not collected:
        logger.warning('proxies: ничего не скачалось')
        return 0

    lines = ['# auto-downloaded by proxy_fetcher'] + sorted(collected)
    if append and proxies_file.exists():
        existing = [l for l in proxies_file.read_text(encoding='utf-8').splitlines()
                    if l.strip() and not l.strip().startswith('#')]
        all_lines = ['# auto-downloaded'] + sorted(set(existing) | collected)
        proxies_file.write_text('\n'.join(all_lines), encoding='utf-8')
    else:
        proxies_file.write_text('\n'.join(lines), encoding='utf-8')

    logger.info(f'proxies.txt: {len(collected)} прокси сохранено')
    return len(collected)


def ensure_proxies(min_working=15):
    """Если рабочих прокси мало — подкачивает."""
    from src.services.proxy_rotator import get_proxy_rotator
    pr = get_proxy_rotator()
    if pr.count >= min_working:
        return pr.count
    logger.info(f'Proxy: рабочих {pr.count} < {min_working}, подкачиваю свежие')
    n = fetch_proxies(limit_total=1500, append=True)
    if n:
        pr.reload()
        pr.verify()
    return pr.count
