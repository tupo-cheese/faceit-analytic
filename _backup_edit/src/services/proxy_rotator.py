"""Менеджер прокси. Soft-blacklist: прокси спит 90s и возвращается."""
import random
import time
import logging
import threading
import concurrent.futures
from pathlib import Path

logger = logging.getLogger('faceit_analytics')

SLEEP_AFTER_FAILS = 2
SLEEP_DURATION = 30


class ProxyRotator:
    _instance = None
    _create_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._create_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, proxies_file=None):
        if hasattr(self, '_init_done'):
            return
        self._init_done = True
        from src.config import DATA_DIR
        self.proxies_file = (Path(proxies_file) if proxies_file
                              else DATA_DIR / 'proxies.txt')
        self.working_file = DATA_DIR / 'proxies_working.txt'
        self._all = []
        self._verified = []
        self._verified_loaded = False
        self._verify_lock = threading.Lock()
        self._lock = threading.Lock()
        self._fails = {}
        self._sleep_until = {}    # proxy -> timestamp до которого "спит"
        self._stats = {'ok': 0, 'fail': 0, 'sleep': 0}
        self._load()

    def _load(self):
        if not self.proxies_file.exists():
            return
        try:
            lines = self.proxies_file.read_text(encoding='utf-8').splitlines()
            self._all = [l.strip() for l in lines
                         if l.strip() and not l.strip().startswith('#')]
            self._all = [p if '://' in p else f'http://{p}' for p in self._all]
            logger.info(f'Proxy: загружено {len(self._all)} строк')
        except Exception as e:
            logger.warning(f'Proxy: err {e}')

        if self.working_file.exists():
            try:
                lines = self.working_file.read_text(encoding='utf-8').splitlines()
                self._verified = [l.strip() for l in lines
                                   if l.strip() and not l.strip().startswith('#')]
                if self._verified:
                    self._verified_loaded = True
                    logger.info(f'Proxy: загружено {len(self._verified)} из кэша')
            except Exception:
                pass

    def _probe(self, proxy, probe_url, timeout):
        try:
            from curl_cffi import requests as cffi
            r = cffi.get(probe_url, impersonate='chrome120',
                          proxies={'https': proxy, 'http': proxy},
                          timeout=timeout)
            return (proxy, r.status_code)
        except Exception:
            return (proxy, None)

    def verify(self, probe_url='https://api.faceit.com/', timeout=5, workers=100):
        with self._verify_lock:
            if getattr(self, '_verifying', False):
                for _ in range(60):
                    time.sleep(1)
                    if not getattr(self, '_verifying', False):
                        return len(self._verified)
                return len(self._verified)
            self._verifying = True
        try:
            return self._verify_inner(probe_url, timeout, workers)
        finally:
            self._verifying = False

    def _verify_inner(self, probe_url, timeout, workers):
        if not self._all:
            return 0
        logger.info(f'Proxy: проверяю {len(self._all)} ({workers} потоков, '
                    f'timeout {timeout}s)…')
        working = []
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(self._probe, p, probe_url, timeout)
                       for p in self._all]
            for f in concurrent.futures.as_completed(futures):
                done += 1
                p, status = f.result()
                if status is not None:
                    working.append(p)
                if done % 200 == 0:
                    logger.info(f'  {done}/{len(self._all)}, рабочих {len(working)}')
        self._verified = working
        self._verified_loaded = True
        try:
            self.working_file.write_text('\n'.join(working), encoding='utf-8')
        except Exception:
            pass
        logger.info(f'Proxy: ✅ {len(working)}/{len(self._all)} '
                    f'({100*len(working)//max(len(self._all),1)}%)')
        return len(working)

    def _ensure_verified(self):
        if self._verified_loaded:
            return
        with self._verify_lock:
            if self._verified_loaded:
                return
            if not self._all:
                try:
                    from src.services.proxy_fetcher import fetch_proxies
                    logger.info('Proxy: пул пуст, авто-загрузка')
                    fetch_proxies(limit_total=1500, append=False)
                    self.reload()
                except Exception as e:
                    logger.warning(f'auto-fetch err: {e}')
            self.verify()

    def get(self):
        """Случайный прокси, не в sleep-режиме."""
        self._ensure_verified()
        now = time.time()
        with self._lock:
            awake = [p for p in self._verified
                     if self._sleep_until.get(p, 0) < now]
            if not awake:
                # все спят — разбудим самых "отдохнувших"
                if self._verified:
                    oldest = sorted(self._verified,
                                     key=lambda p: self._sleep_until.get(p, 0))[:20]
                    for p in oldest:
                        self._sleep_until.pop(p, None)
                    awake = oldest
                else:
                    return None
            p = random.choice(awake)
        return {'https': p, 'http': p}

    def report_fail(self, proxy_dict):
        if not proxy_dict:
            return
        p = proxy_dict.get('https')
        if not p:
            return
        with self._lock:
            self._stats['fail'] += 1
            self._fails[p] = self._fails.get(p, 0) + 1
            if self._fails[p] >= SLEEP_AFTER_FAILS:
                self._sleep_until[p] = time.time() + SLEEP_DURATION
                self._fails[p] = 0
                self._stats['sleep'] += 1

    def report_ok(self, proxy_dict):
        if not proxy_dict:
            return
        p = proxy_dict.get('https')
        if not p:
            return
        with self._lock:
            self._stats['ok'] += 1
            self._fails[p] = 0
            self._sleep_until.pop(p, None)

    def reload(self):
        self._all = []
        self._verified = []
        self._verified_loaded = False
        self._fails.clear()
        self._sleep_until.clear()
        try:
            self.working_file.unlink(missing_ok=True)
        except Exception:
            pass
        self._load()

    @property
    def count(self):
        now = time.time()
        return len([p for p in self._verified
                    if self._sleep_until.get(p, 0) < now])

    @property
    def total(self):
        return len(self._all)

    @property
    def sleeping(self):
        now = time.time()
        return len([p for p in self._verified
                    if self._sleep_until.get(p, 0) >= now])

    def stats(self):
        return dict(self._stats)


_rotator = None


def get_proxy_rotator():
    global _rotator
    if _rotator is None:
        _rotator = ProxyRotator()
    return _rotator
