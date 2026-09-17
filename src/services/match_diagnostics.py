"""
Модуль комплексной диагностики получения матчей.
Тестирует все возможные способы: API, парсинг HTML, headless browser, обход Cloudflare.
"""
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional
import traceback

logger = None  # Будет установлен извне


class MatchDiagnostics:
    """Комплексная диагностика получения матчей со всех источников."""

    def __init__(self, steam_id: str, cache=None):
        self.steam_id = steam_id
        self.cache = cache
        self.results = {}
        self.debug_dir = Path.cwd() / "data" / "debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════
    # ГЛАВНЫЙ МЕТОД — запускает ВСЕ тесты
    # ══════════════════════════════════════════════════════
    async def run_all(self):
        """Запускает все тесты и возвращает полный отчёт."""
        log = logger.info if logger else print

        log("=" * 70)
        log(f"  КОМПЛЕКСНАЯ ДИАГНОСТИКА МАТЧЕЙ для {self.steam_id}")
        log("=" * 70)

        # 1. CSStats — HTML парсинг
        await self._test_csstats_html()

        # 2. CSStats — попытка API
        await self._test_csstats_api()

        # 3. CSStats — поиск match links в HTML
        await self._test_csstats_match_links()

        # 4. FaceitAnalyser — HTML
        await self._test_faceitanalyser_html()

        # 5. FaceitAnalyser — API
        await self._test_faceitanalyser_api()

        # 6. FACEIT — публичный API (steamgpt)
        await self._test_faceit_steamgpt()

        # 7. FACEIT — прямой API (без ключа)
        await self._test_faceit_direct()

        # 8. Leetify — API
        await self._test_leetify()

        # 9. Steam Web API — GetMatchHistory (CS2)
        await self._test_steam_match_history()

        # 10. Steam — share code
        await self._test_steam_sharecode()

        # 11. csgostats.gg
        await self._test_csgostats()

        # 12. HLTV
        await self._test_hltv()

        # 13. FaceitSync
        await self._test_faceitsync()

        # 14. Парсинг HTML csstats (сохранённого)
        await self._test_parse_saved_html()

        # 15. Headless browser (Playwright) — если доступен
        await self._test_playwright()

        # 16. Selenium — если доступен
        await self._test_selenium()

        # 17. Поиск в HTML csstats паттернов матчей
        await self._test_csstats_regex_patterns()

        # 18. Попытка через Cloudscraper
        await self._test_cloudscraper()

        # 19. Curl_cffi с разными профилями
        await self._test_curl_profiles()

        # 20. Проверка cookies / сессии
        await self._test_cookies()

        # Итог
        self._print_summary()
        return self.results

    # ══════════════════════════════════════════════════════
    # ТЕСТ 1: CSStats HTML
    # ══════════════════════════════════════════════════════
    async def _test_csstats_html(self):
        log = logger.info if logger else print
        log("\n[1] CSStats HTML парсинг...")
        try:
            from curl_cffi import requests as cffi_requests
            for profile in ["chrome124", "chrome120", "chrome110",
                            "edge101", "safari17_0"]:
                try:
                    url = f"https://csstats.gg/player/{self.steam_id}"
                    r = cffi_requests.get(
                        url, impersonate=profile, timeout=25)
                    ok = (r.status_code == 200 and
                          "Just a moment" not in r.text[:500])
                    log(f"  [{profile}] HTTP {r.status_code}, "
                        f"len={len(r.text)}, ok={ok}")
                    if ok:
                        out = self.debug_dir / f"csstats_{self.steam_id}.html"
                        out.write_text(r.text, encoding="utf-8")
                        log(f"  ✅ Сохранено: {out}")
                        self.results["csstats_html"] = {
                            "status": "OK", "profile": profile,
                            "len": len(r.text), "file": str(out)}
                        return
                except Exception as e:
                    log(f"  [{profile}] ❌ {e}")
            self.results["csstats_html"] = {"status": "FAIL"}
        except Exception as e:
            log(f"  ❌ Ошибка: {e}")
            self.results["csstats_html"] = {"status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 2: CSStats API
    # ══════════════════════════════════════════════════════
    async def _test_csstats_api(self):
        log = logger.info if logger else print
        log("\n[2] CSStats API попытки...")
        endpoints = [
            f"https://csstats.gg/api/player/{self.steam_id}",
            f"https://csstats.gg/api/v1/player/{self.steam_id}",
            f"https://csstats.gg/api/player/{self.steam_id}/matches",
            f"https://csstats.gg/api/v1/matches/{self.steam_id}",
        ]
        from curl_cffi import requests as cffi_requests
        for url in endpoints:
            try:
                r = cffi_requests.get(
                    url, impersonate="chrome124", timeout=15)
                log(f"  {url}: HTTP {r.status_code}")
                if r.status_code == 200:
                    try:
                        data = r.json()
                        log(f"    JSON OK: {str(data)[:200]}")
                        self.results["csstats_api"] = {
                            "status": "OK", "url": url}
                        return
                    except Exception:
                        log(f"    Не JSON: {r.text[:100]}")
            except Exception as e:
                log(f"  {url}: ❌ {e}")
        self.results["csstats_api"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 3: CSStats — поиск ссылок на матчи в HTML
    # ══════════════════════════════════════════════════════
    async def _test_csstats_match_links(self):
        log = logger.info if logger else print
        log("\n[3] CSStats — поиск match links в HTML...")
        html_file = self.debug_dir / f"csstats_{self.steam_id}.html"
        if not html_file.exists():
            log("  ❌ HTML файл не найден")
            self.results["csstats_links"] = {"status": "NO_FILE"}
            return
        html = html_file.read_text(encoding="utf-8")
        patterns = [
            r'href="/match/(\d+)"',
            r'href="/match/([a-f0-9-]+)"',
            r'data-match-id="(\d+)"',
            r'match_id["\s:=]+(\d+)',
        ]
        found = []
        for pat in patterns:
            matches = re.findall(pat, html)
            log(f"  Паттерн {pat}: найдено {len(matches)}")
            found.extend(matches[:5])
        if found:
            log(f"  ✅ Найдено match IDs: {found[:10]}")
            self.results["csstats_links"] = {
                "status": "OK", "count": len(found),
                "sample": found[:10]}
        else:
            log("  ❌ Матчи не найдены в HTML")
            # Сохраним часть HTML для анализа
            sample_file = self.debug_dir / "csstats_sample.html"
            sample_file.write_text(html[:50000], encoding="utf-8")
            self.results["csstats_links"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 4: FaceitAnalyser HTML
    # ══════════════════════════════════════════════════════
    async def _test_faceitanalyser_html(self):
        log = logger.info if logger else print
        log("\n[4] FaceitAnalyser HTML...")
        try:
            from curl_cffi import requests as cffi_requests
            for profile in ["chrome124", "chrome120", "safari17_0"]:
                try:
                    url = f"https://faceitanalyser.com/player/{self.steam_id}"
                    r = cffi_requests.get(
                        url, impersonate=profile, timeout=25)
                    log(f"  [{profile}] HTTP {r.status_code}, "
                        f"len={len(r.text)}")
                    if r.status_code == 200:
                        out = self.debug_dir / f"fa_{self.steam_id}.html"
                        out.write_text(r.text, encoding="utf-8")
                        log(f"  ✅ Сохранено: {out}")
                        self.results["faceitanalyser_html"] = {
                            "status": "OK", "profile": profile,
                            "len": len(r.text), "file": str(out)}
                        return
                except Exception as e:
                    log(f"  [{profile}] ❌ {e}")
            self.results["faceitanalyser_html"] = {"status": "FAIL"}
        except Exception as e:
            log(f"  ❌ Ошибка: {e}")
            self.results["faceitanalyser_html"] = {
                "status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 5: FaceitAnalyser API
    # ══════════════════════════════════════════════════════
    async def _test_faceitanalyser_api(self):
        log = logger.info if logger else print
        log("\n[5] FaceitAnalyser API...")
        endpoints = [
            f"https://faceitanalyser.com/api/stats/{self.steam_id}",
            f"https://faceitanalyser.com/api/stats/{self.steam_id}/cs2",
            f"https://faceitanalyser.com/api/matches/{self.steam_id}",
        ]
        from curl_cffi import requests as cffi_requests
        for url in endpoints:
            try:
                r = cffi_requests.get(
                    url, impersonate="chrome124", timeout=15)
                log(f"  {url}: HTTP {r.status_code}")
                if r.status_code == 200:
                    log(f"    Data: {r.text[:300]}")
                    self.results["faceitanalyser_api"] = {
                        "status": "OK", "url": url}
                    return
            except Exception as e:
                log(f"  ❌ {e}")
        self.results["faceitanalyser_api"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 6: FACEIT через steamgpt
    # ══════════════════════════════════════════════════════
    async def _test_faceit_steamgpt(self):
        log = logger.info if logger else print
        log("\n[6] FACEIT через steamgpt.net...")
        try:
            from curl_cffi import requests as cffi_requests
            url = f"https://steamgpt.net/faceit/{self.steam_id}.json"
            r = cffi_requests.get(url, impersonate="chrome124", timeout=20)
            log(f"  HTTP {r.status_code}, len={len(r.text)}")
            if r.status_code == 200:
                data = r.json()
                log(f"  Result: {data.get('result')}")
                faceit = data.get("data", {}).get("faceit", {})
                log(f"  Nickname: {faceit.get('nickname')}")
                log(f"  Level: {faceit.get('games', {}).get('cs2', {}).get('skill_level')}")
                self.results["faceit_steamgpt"] = {
                    "status": "OK",
                    "nickname": faceit.get("nickname"),
                    "level": faceit.get("games", {}).get("cs2", {}).get("skill_level")}
        except Exception as e:
            log(f"  ❌ {e}")
            self.results["faceit_steamgpt"] = {
                "status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 7: FACEIT прямой API (без ключа)
    # ══════════════════════════════════════════════════════
    async def _test_faceit_direct(self):
        log = logger.info if logger else print
        log("\n[7] FACEIT прямой API...")
        endpoints = [
            f"https://open.faceit.com/data/v4/players?game=cs2&game_player_id={self.steam_id}",
            f"https://api.faceit.com/core/v1/players?game=cs2&game_player_id={self.steam_id}",
        ]
        from curl_cffi import requests as cffi_requests
        for url in endpoints:
            try:
                r = cffi_requests.get(
                    url,
                    headers={"Accept": "application/json"},
                    impersonate="chrome124", timeout=15)
                log(f"  {url[:60]}...: HTTP {r.status_code}")
                if r.status_code == 200:
                    log(f"    OK: {r.text[:200]}")
                    self.results["faceit_direct"] = {
                        "status": "OK", "url": url}
                    return
            except Exception as e:
                log(f"  ❌ {e}")
        self.results["faceit_direct"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 8: Leetify API
    # ══════════════════════════════════════════════════════
    async def _test_leetify(self):
        log = logger.info if logger else print
        log("\n[8] Leetify API...")
        import aiohttp
        endpoints = [
            f"https://api-public.cs-prod.leetify.com/v3/profile?steam64_id={self.steam_id}",
            f"https://api-public.cs-prod.leetify.com/v3/profile/matches?steam64_id={self.steam_id}",
        ]
        async with aiohttp.ClientSession(
                headers={"User-Agent": "FaceitAnalytics/1.0",
                         "Accept": "application/json"}) as session:
            for url in endpoints:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                        log(f"  {url[:70]}...: HTTP {r.status}")
                        if r.status == 200:
                            data = await r.json()
                            if isinstance(data, list):
                                log(f"    Массив, элементов: {len(data)}")
                            else:
                                log(f"    Ключи: {list(data.keys())[:10]}")
                            self.results["leetify"] = {
                                "status": "OK", "url": url,
                                "count": len(data) if isinstance(data, list) else "object"}
                            return
                except Exception as e:
                    log(f"  ❌ {e}")
        self.results["leetify"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 9: Steam Web API — GetMatchHistory
    # ══════════════════════════════════════════════════════
    async def _test_steam_match_history(self):
        log = logger.info if logger else print
        log("\n[9] Steam Web API GetMatchHistory (CS2)...")
        # CS2 использует app_id 730, но GetMatchHistory работает только для Dota 2
        # Проверим, есть ли endpoint для CS2
        endpoints = [
            f"https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v2/?appid=730&steamid={self.steam_id}",
            f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=730",
        ]
        from curl_cffi import requests as cffi_requests
        for url in endpoints:
            try:
                r = cffi_requests.get(url, impersonate="chrome124", timeout=15)
                log(f"  {url[:70]}...: HTTP {r.status_code}")
                if r.status_code == 200:
                    log(f"    Response: {r.text[:300]}")
                    self.results["steam_match_history"] = {
                        "status": "OK", "url": url, "response": r.text[:500]}
                    return
            except Exception as e:
                log(f"  ❌ {e}")
        self.results["steam_match_history"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 10: Steam share code
    # ══════════════════════════════════════════════════════
    async def _test_steam_sharecode(self):
        log = logger.info if logger else print
        log("\n[10] Steam share code (проверка формата)...")
        # Share code требует авторизации, проверим доступность endpoint
        log("  ⚠️  Share code требует Steam-авторизации, пропуск")
        self.results["steam_sharecode"] = {"status": "NEED_AUTH"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 11: csgostats.gg
    # ══════════════════════════════════════════════════════
    async def _test_csgostats(self):
        log = logger.info if logger else print
        log("\n[11] csgostats.gg...")
        from curl_cffi import requests as cffi_requests
        for profile in ["chrome124", "chrome120"]:
            try:
                url = f"https://csgostats.gg/player/{self.steam_id}"
                r = cffi_requests.get(
                    url, impersonate=profile, timeout=25)
                log(f"  [{profile}] HTTP {r.status_code}, len={len(r.text)}")
                if r.status_code == 200:
                    out = self.debug_dir / f"csgostats_{self.steam_id}.html"
                    out.write_text(r.text, encoding="utf-8")
                    log(f"  ✅ Сохранено: {out}")
                    self.results["csgostats"] = {
                        "status": "OK", "profile": profile, "len": len(r.text)}
                    return
            except Exception as e:
                log(f"  [{profile}] ❌ {e}")
        self.results["csgostats"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 12: HLTV
    # ══════════════════════════════════════════════════════
    async def _test_hltv(self):
        log = logger.info if logger else print
        log("\n[12] HLTV...")
        log("  ⚠️  HLTV блокирует автоматические запросы, требуется headless browser")
        self.results["hltv"] = {"status": "BLOCKED"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 13: FaceitSync
    # ══════════════════════════════════════════════════════
    async def _test_faceitsync(self):
        log = logger.info if logger else print
        log("\n[13] FaceitSync...")
        from curl_cffi import requests as cffi_requests
        try:
            url = f"https://faceitsync.com/player/{self.steam_id}"
            r = cffi_requests.get(
                url, impersonate="chrome124", timeout=25)
            log(f"  HTTP {r.status_code}, len={len(r.text)}")
            if r.status_code == 200:
                out = self.debug_dir / f"faceitsync_{self.steam_id}.html"
                out.write_text(r.text, encoding="utf-8")
                log(f"  ✅ Сохранено: {out}")
                self.results["faceitsync"] = {
                    "status": "OK", "len": len(r.text)}
                return
        except Exception as e:
            log(f"  ❌ {e}")
        self.results["faceitsync"] = {"status": "FAIL"}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 14: Парсинг сохранённого HTML
    # ══════════════════════════════════════════════════════
    async def _test_parse_saved_html(self):
        log = logger.info if logger else print
        log("\n[14] Парсинг сохранённого HTML csstats...")
        html_file = self.debug_dir / f"csstats_{self.steam_id}.html"
        if not html_file.exists():
            log("  ❌ Файл не найден")
            self.results["parse_html"] = {"status": "NO_FILE"}
            return
        html = html_file.read_text(encoding="utf-8")
        # Ищем K/D, ADR, HS%
        kd = re.search(r'K/D Ratio[^0-9]*([\d.]+)', html)
        adr = re.search(r'ADR[^0-9]*([\d.]+)', html)
        hs = re.search(r'HS%[^0-9]*([\d.]+)', html)
        log(f"  K/D: {kd.group(1) if kd else '?'}")
        log(f"  ADR: {adr.group(1) if adr else '?'}")
        log(f"  HS%: {hs.group(1) if hs else '?'}")
        # Ищем матчи
        match_links = re.findall(r'href="/match/(\d+)"', html)
        log(f"  Match links: {len(match_links)}")
        self.results["parse_html"] = {
            "status": "OK", "kd": kd.group(1) if kd else None,
            "adr": adr.group(1) if adr else None,
            "hs": hs.group(1) if hs else None,
            "match_links": len(match_links)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 15: Playwright (headless browser)
    # ══════════════════════════════════════════════════════
    async def _test_playwright(self):
        log = logger.info if logger else print
        log("\n[15] Playwright (headless browser)...")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(
                    f"https://csstats.gg/player/{self.steam_id}",
                    wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                html = await page.content()
                log(f"  ✅ HTML получен, len={len(html)}")
                out = self.debug_dir / f"playwright_csstats_{self.steam_id}.html"
                out.write_text(html, encoding="utf-8")
                await browser.close()
                self.results["playwright"] = {
                    "status": "OK", "len": len(html)}
        except ImportError:
            log("  ⚠️  Playwright не установлен")
            self.results["playwright"] = {"status": "NOT_INSTALLED"}
        except Exception as e:
            log(f"  ❌ {e}")
            self.results["playwright"] = {"status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 16: Selenium
    # ══════════════════════════════════════════════════════
    async def _test_selenium(self):
        log = logger.info if logger else print
        log("\n[16] Selenium...")
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            opts = Options()
            opts.add_argument("--headless")
            driver = webdriver.Chrome(options=opts)
            driver.get(f"https://csstats.gg/player/{self.steam_id}")
            time.sleep(5)
            html = driver.page_source
            log(f"  ✅ HTML получен, len={len(html)}")
            out = self.debug_dir / f"selenium_csstats_{self.steam_id}.html"
            out.write_text(html, encoding="utf-8")
            driver.quit()
            self.results["selenium"] = {"status": "OK", "len": len(html)}
        except ImportError:
            log("  ⚠️  Selenium не установлен")
            self.results["selenium"] = {"status": "NOT_INSTALLED"}
        except Exception as e:
            log(f"  ❌ {e}")
            self.results["selenium"] = {"status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 17: CSStats regex паттерны
    # ══════════════════════════════════════════════════════
    async def _test_csstats_regex_patterns(self):
        log = logger.info if logger else print
        log("\n[17] CSStats — детальный regex анализ HTML...")
        html_file = self.debug_dir / f"csstats_{self.steam_id}.html"
        if not html_file.exists():
            log("  ❌ Файл не найден")
            self.results["csstats_regex"] = {"status": "NO_FILE"}
            return
        html = html_file.read_text(encoding="utf-8")
        # Расширенные паттерны
        patterns = {
            "match_href": r'href="/match/(\d+)"',
            "match_data": r'data-match-id="(\d+)"',
            "match_json": r'"match_id"\s*:\s*"(\d+)"',
            "match_url": r'/match/([a-f0-9-]{36})',
        }
        found = {}
        for name, pat in patterns.items():
            matches = re.findall(pat, html)
            found[name] = len(matches)
            if matches:
                log(f"  {name}: {len(matches)} (пример: {matches[:3]})")
        self.results["csstats_regex"] = {"status": "OK", "patterns": found}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 18: Cloudscraper
    # ══════════════════════════════════════════════════════
    async def _test_cloudscraper(self):
        log = logger.info if logger else print
        log("\n[18] Cloudscraper...")
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            r = scraper.get(f"https://csstats.gg/player/{self.steam_id}")
            log(f"  HTTP {r.status_code}, len={len(r.text)}")
            if r.status_code == 200:
                out = self.debug_dir / f"cloudscraper_csstats_{self.steam_id}.html"
                out.write_text(r.text, encoding="utf-8")
                log(f"  ✅ Сохранено: {out}")
                self.results["cloudscraper"] = {
                    "status": "OK", "len": len(r.text)}
                return
        except ImportError:
            log("  ⚠️  Cloudscraper не установлен")
            self.results["cloudscraper"] = {"status": "NOT_INSTALLED"}
        except Exception as e:
            log(f"  ❌ {e}")
            self.results["cloudscraper"] = {"status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ТЕСТ 19: Curl_cffi все профили
    # ══════════════════════════════════════════════════════
    async def _test_curl_profiles(self):
        log = logger.info if logger else print
        log("\n[19] Curl_cffi — все impersonate профили...")
        from curl_cffi import requests as cffi_requests
        profiles = ["chrome124", "chrome123", "chrome120", "chrome110",
                    "chrome104", "chrome101", "chrome100",
                    "edge101", "edge99", "safari17_0", "safari15_5"]
        url = f"https://csstats.gg/player/{self.steam_id}"
        results = {}
        for p in profiles:
            try:
                r = cffi_requests.get(
                    url, impersonate=p, timeout=20)
                ok = r.status_code == 200 and "Just a moment" not in r.text[:500]
                results[p] = f"{r.status_code} {'OK' if ok else 'BLOCKED'}"
                log(f"  [{p}] HTTP {r.status_code}, ok={ok}")
            except Exception as e:
                results[p] = f"ERR: {e}"
        self.results["curl_profiles"] = results

    # ══════════════════════════════════════════════════════
    # ТЕСТ 20: Cookies / сессия
    # ══════════════════════════════════════════════════════
    async def _test_cookies(self):
        log = logger.info if logger else print
        log("\n[20] Cookies / сессия...")
        try:
            import browser_cookie3
            for name, loader in [
                    ("chrome", browser_cookie3.chrome),
                    ("edge", browser_cookie3.edge),
                    ("firefox", browser_cookie3.firefox)]:
                try:
                    cj = loader(domain_name="csstats.gg")
                    count = len(list(cj))
                    log(f"  {name}: {count} cookies для csstats.gg")
                    if count > 0:
                        self.results["cookies"] = {
                            "status": "OK", "browser": name, "count": count}
                        return
                except Exception as e:
                    log(f"  {name}: ❌ {e}")
            self.results["cookies"] = {"status": "NO_COOKIES"}
        except Exception as e:
            log(f"  ❌ {e}")
            self.results["cookies"] = {"status": "ERROR", "error": str(e)}

    # ══════════════════════════════════════════════════════
    # ИТОГОВЫЙ ОТЧЁТ
    # ══════════════════════════════════════════════════════
    def _print_summary(self):
        log = logger.info if logger else print
        log("\n" + "=" * 70)
        log("  ИТОГОВЫЙ ОТЧЁТ")
        log("=" * 70)
        for key, val in self.results.items():
            status = val.get("status", "?") if isinstance(val, dict) else "?"
            icon = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
            log(f"  {icon} {key}: {status}")
            if isinstance(val, dict):
                for k, v in val.items():
                    if k != "status" and not isinstance(v, (dict, list)):
                        log(f"      {k}: {v}")
        log("\n" + "=" * 70)
        log("  ДИАГНОСТИКА ЗАВЕРШЕНА")
        log("=" * 70)


async def run_diagnostics(steam_id: str, cache=None):
    """Запускает полную диагностику и возвращает результаты."""
    diag = MatchDiagnostics(steam_id, cache)
    return await diag.run_all()
