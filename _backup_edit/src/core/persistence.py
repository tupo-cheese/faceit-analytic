import time
import logging
import orjson
from pathlib import Path

logger = logging.getLogger('faceit_analytics')


def _sanitize(obj):
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)


class DeepCache:
    """Хранилище полных deep-результатов на диске."""

    def __init__(self):
        from src.config import DATA_DIR
        self.dir = DATA_DIR / 'deep_cache'
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, steam_id, full_result, matches, elo_limit=30):
        try:
            path = self.dir / f'{steam_id}.json'
            payload = {
                'saved_at': time.time(),
                'steam_id': steam_id,
                'elo_limit': elo_limit,
                'result': _sanitize(full_result),
                'matches': _sanitize(matches),
            }
            path.write_bytes(orjson.dumps(payload))
            logger.info(f'  💾 deep сохранён: {path.name} ({len(matches)} матчей)')
            return True
        except Exception as e:
            logger.warning(f'  persist save err: {e}')
            return False

    def load(self, steam_id):
        path = self.dir / f'{steam_id}.json'
        if not path.exists():
            return None
        try:
            data = orjson.loads(path.read_bytes())
            logger.info(f'  📂 deep из диска: {len(data.get("matches", []))} матчей, '
                        f'saved {int(time.time() - data.get("saved_at", 0))}s назад')
            return data
        except Exception as e:
            logger.warning(f'  persist load err: {e}')
            return None

    def delete(self, steam_id):
        path = self.dir / f'{steam_id}.json'
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    def list_saved(self):
        out = []
        for p in sorted(self.dir.glob('*.json')):
            try:
                data = orjson.loads(p.read_bytes())
                out.append((p.stem, data.get('saved_at', 0),
                            len(data.get('matches', []))))
            except Exception:
                continue
        return out


_cache = None


def get_deep_cache():
    global _cache
    if _cache is None:
        _cache = DeepCache()
    return _cache
