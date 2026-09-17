"""Парсинг FACEIT match-room HTML — 10 игроков матча."""
import re
import json
from pathlib import Path

logger = None


def _log(msg):
    if logger:
        logger.info(msg)
    else:
        print(msg)


class MatchRoomParser:
    """Извлекает игроков из FACEIT match-room HTML."""

    def __init__(self, html: str, match_id: str = ""):
        self.html = html
        self.match_id = match_id

    def extract_players(self) -> list[dict]:
        """Возвращает список из ~10 игроков с их статистикой."""
        players = {}

        # 1) Ищем в __NEXT_DATA__ (Next.js)
        m = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            self.html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                self._walk(data, players)
            except Exception as e:
                _log(f"  __NEXT_DATA__ parse error: {e}")

        # 2) Ищем в application/json
        for sm in re.finditer(
                r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                self.html, re.S):
            try:
                data = json.loads(sm.group(1))
                self._walk(data, players)
            except Exception:
                pass

        # 3) Regex по embedded JSON с никнеймами + статистикой
        if len(players) < 5:
            self._regex_extract(players)

        # Дедупликация по playerId/nickname
        seen = set()
        result = []
        for key, p in players.items():
            k = p.get("playerId") or p.get("nickname", "")
            if not k or k in seen:
                continue
            seen.add(k)
            result.append(p)
        return result

    def _walk(self, obj, players, depth=0):
        if depth > 15:
            return
        if isinstance(obj, dict):
            # Похоже на игрока?
            nick = obj.get("nickname")
            pid = obj.get("playerId") or obj.get("player_id")
            stats = obj.get("player_stats") or obj.get("stats") or {}

            if nick and (pid or stats):
                # Извлекаем статистику
                kills = self._int(stats.get("Kills", obj.get("kills", 0)))
                deaths = self._int(stats.get("Deaths", obj.get("deaths", 0)))
                assists = self._int(stats.get("Assists", obj.get("assists", 0)))
                kd = stats.get("K/D Ratio") or stats.get("kd_ratio")
                if not kd and deaths:
                    kd = round(kills / deaths, 2)
                hs = stats.get("Headshots %") or stats.get("headshots_percent")
                adr = stats.get("ADR") or stats.get("adr")
                mvps = self._int(stats.get("MVPs", obj.get("mvps", 0)))
                triple = self._int(stats.get("Triple Kills", 0))
                quadro = self._int(stats.get("Quadro Kills", 0))
                penta = self._int(stats.get("Penta Kills", 0))

                players[pid or nick] = {
                    "nickname": nick,
                    "playerId": pid or "",
                    "avatar": obj.get("avatar", ""),
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "kd_ratio": float(kd) if kd else 0.0,
                    "headshots_percent": float(hs) if hs else 0.0,
                    "adr": float(adr) if adr else 0.0,
                    "mvps": mvps,
                    "triple_kills": triple,
                    "quadro_kills": quadro,
                    "penta_kills": penta,
                }
            for v in obj.values():
                self._walk(v, players, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:200]:
                self._walk(item, players, depth + 1)

    def _regex_extract(self, players):
        """Fallback через regex — ищет пары nickname+stats в JSON."""
        # Ищем паттерны "nickname":"X" ... "Kills":"N"
        for m in re.finditer(
                r'"nickname"\s*:\s*"([^"]+)"[^}]*?'
                r'"Kills"\s*:\s*"(\d+)"[^}]*?'
                r'"Deaths"\s*:\s*"(\d+)"',
                self.html):
            nick = m.group(1)
            if nick in players:
                continue
            players[nick] = {
                "nickname": nick,
                "playerId": "",
                "avatar": "",
                "kills": int(m.group(2)),
                "deaths": int(m.group(3)),
                "assists": 0,
                "kd_ratio": round(int(m.group(2)) / max(int(m.group(3)), 1), 2),
                "headshots_percent": 0.0,
                "adr": 0.0,
                "mvps": 0,
                "triple_kills": 0,
                "quadro_kills": 0,
                "penta_kills": 0,
            }

    @staticmethod
    def _int(v):
        try:
            return int(v)
        except Exception:
            return 0


async def fetch_room_players(match_id: str) -> list[dict]:
    """Скачивает match-room HTML и парсит 10 игроков."""
    from curl_cffi import requests as cffi
    # Используем safari184 — единственный проходит Cloudflare
    for lang in ("en", "ru"):
        url = f"https://www.faceit.com/{lang}/cs2/room/{match_id}/scoreboard"
        try:
            r = cffi.get(url, impersonate="safari184", timeout=25,
                         headers={"Accept-Language": "ru-RU,ru;q=0.9"})
            if r.status_code == 200 and len(r.text) > 5000:
                # Сохраняем для отладки
                debug_dir = Path.cwd() / "data" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / f"room_{match_id}.html").write_text(
                    r.text, encoding="utf-8")
                parser = MatchRoomParser(r.text, match_id)
                return parser.extract_players()
        except Exception as e:
            _log(f"  room fetch error ({lang}): {e}")
    return []
