"""Умный парсер ссылок."""
import re

STEAM_ID_RE = re.compile(r"(7656119\d{10})")
STEAM_VANITY_RE = re.compile(r"steamcommunity\.com/id/([^/?#]+)")

# FACEIT: www.faceit.com/{lang}/players/{nick}  или без lang
FACEIT_NICK_RE = re.compile(
    r"faceit\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?players/([^/?#]+)")
# FACEIT UUID
FACEIT_ID_RE = re.compile(
    r"faceit\.com/.*?/players/([a-f0-9-]{36})")


class LinkParser:
    @staticmethod
    def detect(url):
        url = url.strip()
        if not url:
            return {"platform": "unknown", "value": ""}

        m = STEAM_ID_RE.search(url)
        if m:
            return {"platform": "steam_id", "value": m.group(1)}

        m = STEAM_VANITY_RE.search(url)
        if m:
            return {"platform": "steam_vanity", "value": m.group(1)}

        # UUID до ника, чтобы не перепутать
        m = FACEIT_ID_RE.search(url)
        if m:
            return {"platform": "faceit_id", "value": m.group(1)}

        m = FACEIT_NICK_RE.search(url)
        if m:
            return {"platform": "faceit_nick", "value": m.group(1)}

        if "csstats.gg/player/" in url:
            m = STEAM_ID_RE.search(url)
            if m:
                return {"platform": "steam_id", "value": m.group(1)}

        if "cswatch.gg/player/" in url:
            m = STEAM_ID_RE.search(url)
            if m:
                return {"platform": "steam_id", "value": m.group(1)}

        if "://" not in url and " " not in url:
            return {"platform": "nickname", "value": url}

        return {"platform": "unknown", "value": url}
