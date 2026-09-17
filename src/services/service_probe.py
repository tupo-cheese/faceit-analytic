"""Диагностика сервисов."""
import asyncio
import json
from pathlib import Path

logger = None


def _log(msg):
    if logger:
        logger.info(msg)
    else:
        print(msg)


class ServiceProbe:
    def __init__(self, steam_id: str):
        self.steam_id = steam_id
        self.debug_dir = Path.cwd() / "data" / "debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    async def probe_faceit_match_stats(self, match_id):
        """Тест FACEIT stats API для матча."""
        _log(f"══════ FACEIT MATCH STATS {match_id} ══════")
        from src.data_sources.faceit_stats import FaceitMatchStats
        players = FaceitMatchStats.fetch_match(match_id)
        _log(f"Найдено игроков: {len(players)}")
        for i, p in enumerate(players[:10], 1):
            _log(f"  [{i}] {p.get('nickname')} "
                 f"K/D/A={p.get('kills')}/{p.get('deaths')}/"
                 f"{p.get('assists')} "
                 f"ADR={p.get('adr')} "
                 f"HS%={p.get('headshots_percent')}")
        if players:
            _log(f"  Ключи: {sorted(players[0].keys())}")

    async def probe_leetify(self):
        """Leetify — все эндпоинты без ключа."""
        _log("══════ LEETIFY PROBE ══════")
        import aiohttp
        urls = [
            (f"https://api-public.cs-prod.leetify.com/v3/profile"
             f"?steam64_id={self.steam_id}", "profile_v3"),
            (f"https://api-public.cs-prod.leetify.com/v3/profile/matches"
             f"?steam64_id={self.steam_id}", "matches_v3"),
        ]
        async with aiohttp.ClientSession(
                headers={"Accept": "application/json",
                         "User-Agent": "Mozilla/5.0"}) as s:
            for url, name in urls:
                try:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        _log(f"  [{name}] HTTP {r.status}")
                        if r.status == 200:
                            data = await r.json()
                            if isinstance(data, list):
                                _log(f"    Array: {len(data)}")
                            elif isinstance(data, dict):
                                _log(f"    Keys: {list(data.keys())[:10]}")
                            self._save_json(f"leetify_{name}.json", data)
                except Exception as e:
                    _log(f"  [{name}] ❌ {e}")

    async def probe_csstats(self):
        _log("══════ CSSTATS PROBE ══════")
        from curl_cffi import requests as cffi
        for url in [f"https://csstats.gg/player/{self.steam_id}"]:
            for prof in ["safari184", "chrome120"]:
                try:
                    r = cffi.get(url, impersonate=prof, timeout=25)
                    ok = (r.status_code == 200 and
                          "Just a moment" not in r.text[:500])
                    _log(f"  [{prof}] HTTP {r.status_code}, "
                         f"len={len(r.text)}, ok={ok}")
                    if ok:
                        (self.debug_dir / f"csstats_{self.steam_id}.html"
                         ).write_text(r.text, encoding="utf-8")
                        _log(f"    ✅ Сохранено")
                        return
                except Exception as e:
                    _log(f"  [{prof}] ❌ {e}")

    async def probe_faceitanalyser(self):
        _log("══════ FACEIT ANALYSER PROBE ══════")
        from curl_cffi import requests as cffi
        nick = ""
        try:
            r = cffi.get(f"https://steamgpt.net/faceit/{self.steam_id}.json",
                         impersonate="chrome120", timeout=20)
            if r.status_code == 200:
                nick = r.json().get("data", {}).get(
                    "faceit", {}).get("nickname", "")
        except Exception:
            pass
        if not nick:
            _log("  ❌ Нет ника")
            return
        _log(f"  Ник: {nick}")
        for url in [
                f"https://faceitanalyser.com/player/{nick}",
                f"https://faceitanalyser.com/matches/{nick}"]:
            for prof in ["safari184", "chrome120"]:
                try:
                    r = cffi.get(url, impersonate=prof, timeout=25)
                    ok = r.status_code == 200 and len(r.text) > 3000
                    _log(f"  [{prof}] {url.split('/')[-2]}: "
                         f"HTTP {r.status_code}, len={len(r.text)}, ok={ok}")
                    if ok:
                        (self.debug_dir / f"fa_{url.split('/')[-2]}_{nick}.html"
                         ).write_text(r.text, encoding="utf-8")
                        return
                except Exception:
                    pass

    async def probe_cswatch(self):
        _log("══════ CSWATCH PROBE ══════")
        import aiohttp
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)) as s:
            try:
                async with s.get(
                        f"https://cswatch.gg/api/public/player/{self.steam_id}") as r:
                    if r.status == 200:
                        data = await r.json()
                        _log(f"  Keys: {list(data.keys())}")
                        self._save_json(f"cswatch_{self.steam_id}.json", data)
            except Exception as e:
                _log(f"  ❌ {e}")

    def _save_json(self, name, data):
        try:
            out = self.debug_dir / name
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            _log(f"    💾 {name}")
        except Exception:
            pass


async def run_probe(steam_id: str, services=None):
    p = ServiceProbe(steam_id)
    if not services:
        services = ["faceit", "cswatch", "csstats", "faceitanalyser", "leetify"]
    for s in services:
        try:
            if s == "faceit":
                await p.probe_faceit_match_stats(steam_id)
            elif s == "cswatch":
                await p.probe_cswatch()
            elif s == "csstats":
                await p.probe_csstats()
            elif s == "faceitanalyser":
                await p.probe_faceitanalyser()
            elif s == "leetify":
                await p.probe_leetify()
        except Exception as e:
            _log(f"❌ {s}: {e}")
    _log("\n═══ PROBE ЗАВЕРШЁН ═══")
