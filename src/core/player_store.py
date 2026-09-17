import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('faceit_analytics')


class PlayerStore:
    """История загруженных игроков, сохраняется на диск."""

    def __init__(self):
        from src.config import DATA_DIR
        self.file = DATA_DIR / 'players_index.json'
        self._data = {}
        self._load()

    def _load(self):
        if self.file.exists():
            try:
                self._data = json.loads(self.file.read_text(encoding='utf-8'))
                logger.info(f'PlayerStore: {len(self._data)} записей')
            except Exception:
                self._data = {}

    def _save(self):
        try:
            self.file.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding='utf-8')
        except Exception as e:
            logger.warning(f'PlayerStore save err: {e}')

    def upsert(self, steam_id, **kwargs):
        if not steam_id:
            return
        rec = self._data.setdefault(steam_id, {})
        for k, v in kwargs.items():
            if v not in (None, '', 0, False, []):
                rec[k] = v
        rec['last_loaded'] = datetime.now().isoformat(timespec='seconds')
        self._save()

    def mark_deep(self, steam_id, matches_count=0):
        rec = self._data.setdefault(steam_id, {})
        rec['has_deep'] = True
        rec['deep_matches'] = matches_count
        rec['last_deep'] = datetime.now().isoformat(timespec='seconds')
        self._save()

    def get(self, steam_id):
        return self._data.get(steam_id, {})

    def all(self):
        return dict(self._data)

    def find(self, query):
        q = query.lower().strip()
        if q in self._data:
            return q
        for sid, rec in self._data.items():
            if q == (rec.get('nickname') or '').lower():
                return sid
        for sid, rec in self._data.items():
            if q in (rec.get('nickname') or '').lower():
                return sid
        return None

    def list_sorted(self):
        items = list(self._data.items())
        items.sort(key=lambda x: x[1].get('last_loaded', ''), reverse=True)
        return items


_store = None


def get_player_store():
    global _store
    if _store is None:
        _store = PlayerStore()
    return _store
