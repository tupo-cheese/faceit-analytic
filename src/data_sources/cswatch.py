import aiohttp
import logging
from src.data_sources.base import DataSource

logger = logging.getLogger('faceit_analytics')


class CSWatchSource(DataSource):
    name = 'cswatch'
    BASE = 'https://cswatch.gg/api/public'

    def __init__(self, cache):
        self.cache = cache
        self.session = None

    async def _session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={'User-Agent': 'FaceitAnalytics/1.0',
                         'Accept': 'application/json'})
        return self.session

    async def fetch_player(self, steam_id):
        cached = self.cache.get('cswatch', steam_id)
        if cached:
            return cached
        session = await self._session()
        url = f'{self.BASE}/player/{steam_id}'
        try:
            async with session.get(url) as r:
                if r.status != 200:
                    logger.info(f'  [cswatch] HTTP {r.status}')
                    return None
                data = await r.json()
            bans = data.get('bans', {}) or {}
            result = {
                'steam_id': steam_id,
                'persona_name': data.get('personaName', ''),
                'avatar_url': data.get('avatarUrl', ''),
                'reputation_score': data.get('reputationScore', 0),
                'risk_level': data.get('riskLevel', ''),
                'is_cheater': data.get('isCheater', False),
                'conviction_count': data.get('convictionCount', 0),
                'ai_severity': data.get('aiSeverity', 0),
                'vac_banned': bans.get('vac', False),
                'game_bans': bans.get('gameBans', 0),
                'last_ban_days': bans.get('lastBanDays', 0),
                'cswatch_url': data.get('cswatchProfileUrl', ''),
                'steam_url': data.get('steamProfileUrl', ''),
                'overwatch_bans': bans.get('overwatch', 0),
                'economy_bans': bans.get('economy', 0),
                'community_bans': bans.get('community', 0),
                'trust_factor': data.get('trustFactor', 0),
                'matches_total': data.get('matchesTotal', 0),
                'first_seen': data.get('firstSeen', ''),
                'last_seen': data.get('lastSeen', ''),
                'premier_rating': data.get('premierRating', 0),
            }
            self.cache.set('cswatch', steam_id, result)
            return result
        except Exception as e:
            logger.info(f'  [cswatch] err: {e}')
            return None

    async def fetch_matches(self, steam_id, limit=50):
        return []

    async def close(self):
        if self.session and (not self.session.closed):
            await self.session.close()
