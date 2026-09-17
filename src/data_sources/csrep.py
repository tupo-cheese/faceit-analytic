"""CSRep.gg — Trust Rating, репутация, баны, чат (публичный парсинг)."""
import re
import logging
from curl_cffi import requests as cffi_requests

logger = logging.getLogger("faceit_analytics")


class CSRepSource:
    name = "csrep"
    BASE = "https://csrep.gg"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://csrep.gg/",
    }

    def __init__(self, cache):
        self.cache = cache

    def _get_html(self, url):
        for profile in ["safari184", "chrome124"]:
            try:
                r = cffi_requests.get(url, headers=self.HEADERS,
                                       impersonate=profile, timeout=20)
                if r.status_code == 200 and "Just a moment" not in r.text[:500]:
                    return r.text
            except Exception:
                continue
        return None

    def fetch_player(self, steam_id):
        """Возвращает Trust Rating, репутацию, баны."""
        cached = self.cache.get("csrep", steam_id)
        if cached:
            return cached

        html = self._get_html(f"{self.BASE}/player/{steam_id}")
        if not html:
            return None

        result = {"steam_id": steam_id, "source": "csrep"}

        # Trust Score (0-100)
        m = re.search(r'Trust\s*(?:Rating|Score)[^0-9]*(\d+)', html, re.I)
        if m:
            result["trust_score"] = int(m.group(1))

        # Reputation score
        m = re.search(r'Reputation[^0-9]*(\d+)', html, re.I)
        if m:
            result["reputation_score"] = int(m.group(1))

        # Ban status
        m = re.search(r'(?:VAC|Game|Overwatch)\s*Ban[^<]*?(Yes|No|True|False|Detected)',
                      html, re.I)
        if m:
            result["banned"] = m.group(1).lower() in ("yes", "true", "detected")

        # Overwatch verdict
        m = re.search(r'Overwatch[^<]*?(Guilty|Not Guilty|Pending)',
                      html, re.I)
        if m:
            result["overwatch_verdict"] = m.group(1)

        # Total matches
        m = re.search(r'(\d[\d,]+)\s*Matches', html)
        if m:
            result["matches_total"] = int(m.group(1).replace(",", ""))

        # Win rate
        m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*Win', html)
        if m:
            result["win_rate"] = float(m.group(1))

        # K/D
        m = re.search(r'K/D[^0-9]*([\d.]+)', html, re.I)
        if m:
            result["kd"] = float(m.group(1))

        # ADR
        m = re.search(r'ADR[^0-9]*([\d.]+)', html, re.I)
        if m:
            result["adr"] = float(m.group(1))

        # HS%
        m = re.search(r'HS%[^0-9]*([\d.]+)', html, re.I)
        if m:
            result["hs"] = float(m.group(1))

        # Reaction time (ms)
        m = re.search(r'Reaction[^0-9]*(\d+)', html, re.I)
        if m:
            result["reaction_time"] = int(m.group(1))

        # Pre-aim score
        m = re.search(r'Pre-?[Aa]im[^0-9]*([\d.]+)', html, re.I)
        if m:
            result["preaim"] = float(m.group(1))

        # Crosshair placement
        m = re.search(r'Crosshair[^0-9]*([\d.]+)', html, re.I)
        if m:
            result["crosshair_placement"] = float(m.group(1))

        # Time to damage (ms)
        m = re.search(r'Time\s*to\s*Damage[^0-9]*(\d+)', html, re.I)
        if m:
            result["time_to_damage"] = int(m.group(1))

        # KAST%
        m = re.search(r'KAST[^0-9]*([\d.]+)', html, re.I)
        if m:
            result["kast"] = float(m.group(1))

        # Clutch win rate
        m = re.search(r'Clutch[^0-9]*([\d.]+)%', html, re.I)
        if m:
            result["clutch_winrate"] = float(m.group(1))

        # Entry success
        m = re.search(r'Entry[^0-9]*([\d.]+)%', html, re.I)
        if m:
            result["entry_success"] = float(m.group(1))

        self.cache.set("csrep", steam_id, result)
        return result
