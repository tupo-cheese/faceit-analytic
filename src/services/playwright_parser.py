"""Парсер матчей через Playwright с ожиданием загрузки JS."""
import asyncio
import re
from pathlib import Path

logger = None


class PlaywrightParser:
    def __init__(self, steam_id: str):
        self.steam_id = steam_id
        self.debug_dir = Path.cwd() / "data" / "debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    async def _load_page(self, url: str, scroll: bool = True) -> str:
        """Загружает страницу, ждёт networkidle, прокручивает."""
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US")
            page = await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=60000)
            # Дополнительно ждём Cloudflare-заглушку
            await page.wait_for_timeout(5000)

            if scroll:
                # Прокручиваем вниз, чтобы триггернуть lazy-load матчей
                for _ in range(5):
                    await page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)

            html = await page.content()
            await browser.close()
            return html

    async def fetch_csstats_matches(self, limit: int = 50) -> list[dict]:
        log = logger.info if logger else print
        log(f"  [Playwright] CSStats: {self.steam_id}...")
        try:
            html = await self._load_page(
                f"https://csstats.gg/player/{self.steam_id}")
            out = self.debug_dir / f"pw_csstats_{self.steam_id}.html"
            out.write_text(html, encoding="utf-8")
            log(f"  [Playwright] HTML сохранён ({len(html)} символов)")

            # Проверяем, не Cloudflare ли это
            if "Just a moment" in html[:2000]:
                log("  [Playwright] ❌ Cloudflare всё ещё блокирует")
                return []
            if "challenge" in html[:1000].lower():
                log("  [Playwright] ❌ Cloudflare challenge")
                return []

            matches = self._extract_csstats(html)
            log(f"  [Playwright] Найдено матчей: {len(matches)}")
            return matches[:limit]
        except Exception as e:
            log(f"  [Playwright] Ошибка CSStats: {e}")
            return []

    async def fetch_faceitanalyser_matches(self, limit: int = 50) -> list[dict]:
        log = logger.info if logger else print
        log(f"  [Playwright] FaceitAnalyser: {self.steam_id}...")
        try:
            html = await self._load_page(
                f"https://faceitanalyser.com/player/{self.steam_id}")
            out = self.debug_dir / f"pw_fa_{self.steam_id}.html"
            out.write_text(html, encoding="utf-8")
            log(f"  [Playwright] HTML сохранён ({len(html)} символов)")

            if "Just a moment" in html[:2000]:
                log("  [Playwright] ❌ Cloudflare блокирует")
                return []

            matches = self._extract_fa(html)
            log(f"  [Playwright] FaceitAnalyser матчей: {len(matches)}")
            return matches[:limit]
        except Exception as e:
            log(f"  [Playwright] Ошибка FaceitAnalyser: {e}")
            return []

    def _extract_csstats(self, html: str) -> list[dict]:
        """Гибкий поиск ссылок на матчи в HTML csstats."""
        matches = []
        seen = set()
        # Разные форматы ссылок
        patterns = [
            r'href="[^"]*?/match/(\d+)"',
            r'href="/match/(\d+)"',
            r'href="[^"]*?/match/([a-f0-9]{8,})"',
            r'data-match-id="([a-f0-9-]+)"',
            r'match_id["\s:=]+["\']?(\d{6,})["\']?',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.I):
                mid = m.group(1)
                if mid and mid not in seen:
                    seen.add(mid)
                    matches.append({
                        "id": mid, "match_id": mid,
                        "source": "csstats",
                        "map_name": "", "date": ""})
        return matches

    def _extract_fa(self, html: str) -> list[dict]:
        """Гибкий поиск матчей в HTML faceitanalyser."""
        matches = []
        seen = set()
        patterns = [
            r'href="[^"]*?/match/([a-f0-9-]{20,})"',
            r'href="/match/([a-f0-9-]{20,})"',
            r'matchId["\s:=]+["\']([a-f0-9-]{20,})["\']',
            r'"match_id"\s*:\s*"([a-f0-9-]{20,})"',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.I):
                mid = m.group(1)
                if mid and mid not in seen:
                    seen.add(mid)
                    matches.append({
                        "id": mid, "match_id": mid,
                        "source": "faceitanalyser",
                        "map_name": "", "date": ""})
        return matches

    async def fetch_player_stats(self) -> dict:
        """Метрики игрока (K/D, ADR, HS%) с csstats."""
        log = logger.info if logger else print
        try:
            html = await self._load_page(
                f"https://csstats.gg/player/{self.steam_id}", scroll=False)
            result = {}
            kd = re.search(r'K/D[^0-9]*([\d.]+)', html)
            adr = re.search(r'ADR[^0-9]*([\d.]+)', html)
            hs = re.search(r'HS%[^0-9]*([\d.]+)', html)
            rating = re.search(r'Rating[^0-9]*([\d.]+)', html)
            if kd: result["csstats_kd"] = float(kd.group(1))
            if adr: result["csstats_adr"] = float(adr.group(1))
            if hs: result["csstats_hs"] = float(hs.group(1))
            if rating: result["csstats_rating"] = float(rating.group(1))
            log(f"  [Playwright] Метрики: {result}")
            return result
        except Exception as e:
            log(f"  [Playwright] Ошибка метрик: {e}")
            return {}


async def fetch_matches_via_playwright(steam_id: str, limit: int = 50):
    parser = PlaywrightParser(steam_id)
    cs = await parser.fetch_csstats_matches(limit)
    fa = await parser.fetch_faceitanalyser_matches(limit)
    seen = set()
    unique = []
    for m in cs + fa:
        mid = m.get("match_id")
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(m)
    return unique
