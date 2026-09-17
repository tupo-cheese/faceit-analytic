"""csstats.gg — только safari184."""
import re
import json
from pathlib import Path
from curl_cffi import requests as cffi_requests
from src.data_sources.base import DataSource


class CSStatsSource(DataSource):
    name = "csstats"
    BASE = "https://csstats.gg"
    # safari184 — единственный проходящий Cloudflare
    PROFILE = "safari184"

    def __init__(self, cache):
        self.cache = cache

    def _get_html(self, url):
        try:
            r = cffi_requests.get(
                url, impersonate=self.PROFILE, timeout=30,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                })
            if (r.status_code == 200 and
                    "Just a moment" not in r.text[:500]):
                return r.text
        except Exception:
            pass
        return None

    def _parse_pm(self, html):
        stats = {}
        for m in re.finditer(
                r'<div class="pm-c">\s*'
                r'<span class="k">([^<]+)</span>\s*'
                r'<span class="v">(.*?)</span>\s*</div>',
                html, re.S):
            key = m.group(1).strip()
            val = re.sub(r'<[^>]+>', ' ', m.group(2))
            val = re.sub(r'\s+', ' ', val).strip()
            num = re.search(r'-?\d+\.?\d*', val)
            stats[key] = num.group(0) if num else val
        return stats

    async def fetch_player(self, steam_id):
        cached = self.cache.get("csstats_player", steam_id)
        if cached:
            return cached
        html = self._get_html(f"{self.BASE}/player/{steam_id}")
        if not html:
            return {"steam_id": steam_id, "requires_auth": True}
        result = {"steam_id": steam_id, "source": "csstats",
                  "raw_html_len": len(html)}
        cards = self._parse_pm(html)
        result["cards"] = cards
        # Известные метрики
        for key, patterns in [
                ("kd", [r'K/D(?:\s*Ratio)?[^0-9\-]{0,20}([\d.]+)']),
                ("adr", [r'ADR[^0-9\-]{0,20}([\d.]+)']),
                ("hs", [r'HS%[^0-9\-]{0,20}([\d.]+)']),
                ("rating", [r'Rating[^0-9\-]{0,20}([\d.]+)']),
                ("kills_total", [r'Kills[^0-9\-]{0,20}(\d+)']),
                ("deaths_total", [r'Deaths[^0-9\-]{0,20}(\d+)']),
                ("matches_total", [r'Matches[^0-9\-]{0,20}(\d+)']),
                ("wins", [r'Wins[^0-9\-]{0,20}(\d+)'])]:
            for pat in patterns:
                m = re.search(pat, html, re.I)
                if m:
                    result[key] = m.group(1)
                    break
        m = re.search(r'cs2rating[^"]*"[^>]*style="[^"]*rating\.(\w+)', html)
        if m:
            result["rating_badge"] = m.group(1)
        # Debug
        debug_dir = Path.cwd() / "data" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"csstats_{steam_id}.html").write_text(
            html, encoding="utf-8")
        self.cache.set("csstats_player", steam_id, result)
        return result

    async def fetch_matches(self, steam_id, limit=50):
        return []

    async def close(self):
        pass
