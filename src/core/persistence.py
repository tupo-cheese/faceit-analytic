import time
import logging
import orjson
from pathlib import Path

logger = logging.getLogger('faceit_analytics')


def _normalize(d):
    """Ключи-строки с цифрами → int, чтобы pyqtgraph не падал."""
    if not isinstance(d, dict):
        return d
    out = {}
    for k, v in d.items():
        if isinstance(k, str):
            try:
                out[int(k)] = v
                continue
            except (ValueError, TypeError):
                pass
        out[k] = v
    return out


def _sanitize(obj):
    """Рекурсивно очищает объект для JSON."""
    if obj is None or isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    return str(obj)


class DeepCache:

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
            # OPT_NON_STR_KEYS позволяет сохранить int-ключи словарей
            data = orjson.dumps(payload, option=orjson.OPT_NON_STR_KEYS)
            path.write_bytes(data)
            logger.info(f'  💾 deep сохранён: {path.name} '
                        f'({len(matches)} матчей)')
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
            # нормализуем ключи в бакетах (orjson выдаёт строки)
            res = data.get('result', {})
            for key in ('player', 'teammates', 'enemies', 'friends'):
                if key in res:
                    res[key] = _normalize(res[key])
            # для 'friends' есть ключ '__baseline__' — оставим как есть
            logger.info(f'  📂 deep из диска: '
                        f'{len(data.get("matches", []))} матчей, '
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
