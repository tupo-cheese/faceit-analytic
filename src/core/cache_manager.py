"""Кэш API-ответов с TTL."""
import time
import orjson
import hashlib
from src.config import CACHE_DIR


class CacheManager:
    # TTL по namespace (в секундах)
    TTL = {
        "faceit_matches": 3600,
        "faceit_player": 3600,
        "csstats_player": 3600,
        "steam_player": 3600,
        "cswatch": 3600,
        "leetify": 3600,
        "default": 1800,
    }

    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem = {}

    def _key(self, namespace, key):
        raw = f"{namespace}:{key}".encode()
        return hashlib.sha1(raw).hexdigest()

    def get(self, namespace, key):
        k = self._key(namespace, key)
        ttl = self.TTL.get(namespace, self.TTL["default"])
        if k in self._mem:
            ts, val = self._mem[k]
            if time.time() - ts < ttl:
                return val
            del self._mem[k]
        f = self.cache_dir / f"{k}.json"
        if f.exists():
            try:
                payload = orjson.loads(f.read_bytes())
                ts = payload.get("ts", 0)
                if time.time() - ts < ttl:
                    self._mem[k] = (ts, payload.get("data"))
                    return payload.get("data")
                f.unlink(missing_ok=True)
            except Exception:
                f.unlink(missing_ok=True)
        return None

    def set(self, namespace, key, value):
        k = self._key(namespace, key)
        now = time.time()
        self._mem[k] = (now, value)
        try:
            (self.cache_dir / f"{k}.json").write_bytes(
                orjson.dumps({"ts": now, "data": value}))
        except Exception:
            pass

    def clear(self):
        self._mem.clear()
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)

    def clear_namespace(self, namespace):
        prefix = hashlib.sha1(f"{namespace}:".encode()).hexdigest()[:8]
        for k in list(self._mem.keys()):
            if k.startswith(prefix):
                del self._mem[k]
