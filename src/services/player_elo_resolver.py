"""ELO резолвер с диагностикой и несколькими endpoints."""
import json
import re
import logging
import concurrent.futures
from pathlib import Path
from curl_cffi import requests as cffi_requests

logger = logging.getLogger("faceit_analytics")


class PlayerEloResolver:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": "https://www.faceit.com/",
        "Origin": "https://www.faceit.com",
    }

    def __init__(self):
        self._cache = {}
        self._cache_file = Path.cwd() / "data" / "player_elo_cache.json"
        self._debug_dir = Path.cwd() / "data" / "debug"
        self._debug_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self._cache_file.exists():
            try:
                self._cache = json.loads(
                    self._cache_file.read_text(encoding="utf-8"))
                logger.info(f"ELO cache: {len(self._cache)} записей")
            except Exception:
                pass

    def _save(self):
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _parse_json(self, data):
        """Ищет elo в разных структурах."""
        if not isinstance(data, dict):
            return {}
        # Рекурсивно ищем faceit_elo/skill_level
        def walk(obj, depth=0):
            if depth > 10:
                return None
            if isinstance(obj, dict):
                if "faceit_elo" in obj and obj["faceit_elo"]:
                    return obj
                for v in obj.values():
                    r = walk(v, depth + 1)
                    if r:
                        return r
            elif isinstance(obj, list):
                for item in obj[:5]:
                    r = walk(item, depth + 1)
                    if r:
                        return r
            return None
        target = walk(data)
        if target:
            return {
                "elo": int(target.get("faceit_elo", 0)),
                "level": int(target.get("skill_level", 0)),
                "winrate": float(target.get("win_rate", 0) or
                                 target.get("winRate", 0) or 0),
            }
        return {}

    def _try_endpoint(self, url, is_json=True):
        """Пробует endpoint с разными impersonate."""
        for prof in ["safari184", "chrome120", "chrome124"]:
            try:
                r = cffi_requests.get(url, headers=self.HEADERS,
                                       impersonate=prof, timeout=10)
                if r.status_code != 200:
                    continue
                if is_json:
                    try:
                        data = r.json()
                        result = self._parse_json(data)
                        if result.get("elo"):
                            return result, r.text
                    except Exception:
                        pass
                else:
                    return None, r.text
            except Exception:
                continue
        return None, None

    def _fetch_by_player_id(self, player_id):
        """Через Core API по UUID."""
        if not player_id:
            return {}, None
        urls = [
            f"https://api.faceit.com/core/v1/players/{player_id}",
            f"https://api.faceit.com/users/v1/users/{player_id}",
        ]
        for url in urls:
            result, raw = self._try_endpoint(url, is_json=True)
            if result and result.get("elo"):
                return result, raw
        return {}, None

    def _fetch_html(self, nickname):
        """HTML профиля → __NEXT_DATA__ или inline JSON."""
        if not nickname:
            return {}, None
        import urllib.parse
        nick_q = urllib.parse.quote(nickname.replace(" ", "%20"))
        for url in [
                f"https://www.faceit.com/ru/players/{nick_q}",
                f"https://www.faceit.com/en/players/{nick_q}"]:
            _, raw = self._try_endpoint(url, is_json=False)
            if not raw:
                continue
            result = {}
            # __NEXT_DATA__
            m = re.search(
                r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                raw, re.S)
            if m:
                try:
                    nd = json.loads(m.group(1))
                    result = self._parse_json(nd)
                except Exception:
                    pass
            # inline
            if not result.get("elo"):
                m = re.search(r'"faceit_elo"\s*:\s*(\d+)', raw)
                if m:
                    result["elo"] = int(m.group(1))
            if not result.get("level"):
                m = re.search(r'"skill_level"\s*:\s*(\d+)', raw)
                if m:
                    result["level"] = int(m.group(1))
            if result.get("elo"):
                return result, raw
        return {}, None

    def _fetch_one(self, args):
        nickname, player_id = args
        key = (player_id or nickname or "").lower()
        if not key:
            return key, {}
        if key in self._cache and self._cache[key].get("elo"):
            return key, self._cache[key]

        # 1. Core API
        data, raw = self._fetch_by_player_id(player_id)
        # 2. HTML
        if not data.get("elo"):
            data2, raw2 = self._fetch_html(nickname)
            if data2.get("elo"):
                data = data2
                raw = raw2
        return key, data

    def dump_one(self, nickname="", player_id=""):
        """Полный дамп для одного игрока — для диагностики."""
        logger.info(f"═══ DUMP {nickname} / {player_id} ═══")
        if player_id:
            for url in [
                    f"https://api.faceit.com/core/v1/players/{player_id}",
                    f"https://api.faceit.com/users/v1/users/{player_id}"]:
                for prof in ["safari184", "chrome120"]:
                    try:
                        r = cffi_requests.get(
                            url, headers=self.HEADERS,
                            impersonate=prof, timeout=10)
                        logger.info(f"  [{prof}] {url}")
                        logger.info(f"    HTTP {r.status_code}, "
                                    f"len={len(r.text)}")
                        if r.status_code == 200:
                            try:
                                data = r.json()
                                keys = list(data.keys())[:10]
                                logger.info(f"    keys: {keys}")
                                games = data.get("games", {})
                                if games:
                                    logger.info(f"    games keys: "
                                                f"{list(games.keys())}")
                                    cs2 = games.get("cs2", {})
                                    logger.info(f"    cs2: {cs2}")
                                # Сохраняем
                                (self._debug_dir / "elo_dump.json"
                                 ).write_text(
                                    json.dumps(data, indent=2,
                                               ensure_ascii=False),
                                    encoding="utf-8")
                                return
                            except Exception as e:
                                logger.info(f"    json err: {e}")
                                logger.info(f"    text: {r.text[:200]}")
                    except Exception as e:
                        logger.info(f"    err: {e}")
        if nickname:
            import urllib.parse
            nick_q = urllib.parse.quote(nickname.replace(" ", "%20"))
            url = f"https://www.faceit.com/ru/players/{nick_q}"
            for prof in ["safari184", "chrome120"]:
                try:
                    r = cffi_requests.get(
                        url, headers=self.HEADERS,
                        impersonate=prof, timeout=12)
                    logger.info(f"  [{prof}] {url}: HTTP {r.status_code}, "
                                f"len={len(r.text)}")
                    if r.status_code == 200:
                        # Сохраняем HTML
                        f = self._debug_dir / f"profile_{nickname}.html"
                        f.write_text(r.text, encoding="utf-8")
                        logger.info(f"    saved: {f}")
                        # Ищем ELO
                        m = re.search(r'"faceit_elo"\s*:\s*(\d+)', r.text)
                        logger.info(f"    faceit_elo: "
                                    f"{m.group(1) if m else 'NOT FOUND'}")
                        m = re.search(r'"skill_level"\s*:\s*(\d+)', r.text)
                        logger.info(f"    skill_level: "
                                    f"{m.group(1) if m else 'NOT FOUND'}")
                        return
                except Exception as e:
                    logger.info(f"    err: {e}")

    def batch_get_players(self, players, max_workers=20):
        result = {}
        to_fetch = []
        for p in players:
            nickname = p.get("nickname", "")
            player_id = p.get("player_id", "")
            key = (player_id or nickname or "").lower()
            if not key:
                continue
            if key in self._cache and self._cache[key].get("elo"):
                result[key] = self._cache[key]
            else:
                to_fetch.append((nickname, player_id))

        if not to_fetch:
            return result

        logger.info(f"ELO fetch: {len(to_fetch)} новых, "
                    f"{max_workers} потоков")
        ok = 0
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers) as ex:
            for key, data in ex.map(self._fetch_one, to_fetch):
                if data and data.get("elo"):
                    self._cache[key] = data
                    result[key] = data
                    ok += 1
        logger.info(f"  ✅ получено ELO: {ok}/{len(to_fetch)}")
        self._save()
        return result


_resolver = None


def get_elo_resolver():
    global _resolver
    if _resolver is None:
        _resolver = PlayerEloResolver()
    return _resolver
