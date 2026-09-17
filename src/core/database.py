"""SQLite-менеджер с WAL."""
import sqlite3
import orjson
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config import DB_PATH


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._configure()
        self._migrate()

    def _configure(self):
        c = self.conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-64000")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA mmap_size=268435456")
        c.execute("PRAGMA foreign_keys=ON")
        c.commit()

    def _migrate(self):
        c = self.conn
        c.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            steam_id TEXT PRIMARY KEY,
            faceit_id TEXT,
            nickname TEXT,
            avatar_url TEXT,
            data TEXT,
            last_updated TEXT,
            source TEXT
        );
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            source TEXT,
            date TEXT,
            map_name TEXT,
            avg_elo INTEGER,
            avg_elo_bracket INTEGER,
            data TEXT,
            last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS cheater_verdicts (
            steam_id TEXT PRIMARY KEY,
            probability REAL,
            reasons TEXT,
            calibrated INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_id TEXT,
            predicted REAL,
            actual INTEGER,
            features TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_matches_elo ON matches(avg_elo_bracket);
        CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
        CREATE INDEX IF NOT EXISTS idx_players_nick ON players(nickname);
        """)
        c.commit()

    def upsert_player(self, steam_id, profile, faceit_id="", nickname="",
                      avatar="", source=""):
        data = orjson.dumps(profile).decode()
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """INSERT INTO players(steam_id, faceit_id, nickname, avatar_url, data, last_updated, source)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(steam_id) DO UPDATE SET
                 faceit_id=excluded.faceit_id, nickname=excluded.nickname,
                 avatar_url=excluded.avatar_url, data=excluded.data,
                 last_updated=excluded.last_updated, source=excluded.source""",
            (steam_id, faceit_id, nickname, avatar, data, now, source),
        )
        self.conn.commit()

    def get_player(self, steam_id):
        row = self.conn.execute("SELECT * FROM players WHERE steam_id=?", (steam_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["data"] = orjson.loads(d["data"]) if d["data"] else {}
        return d

    def list_players(self, limit=500):
        rows = self.conn.execute(
            "SELECT steam_id, nickname, avatar_url, last_updated, source FROM players ORDER BY last_updated DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    def search_players(self, query, limit=20):
        like = f"%{query}%"
        rows = self.conn.execute(
            "SELECT steam_id, nickname, avatar_url, last_updated, source FROM players WHERE nickname LIKE ? OR steam_id LIKE ? ORDER BY last_updated DESC LIMIT ?",
            (like, like, limit)).fetchall()
        return [dict(r) for r in rows]

    def upsert_match(self, match_id, source, date, map_name, avg_elo, avg_elo_bracket, data):
        payload = orjson.dumps(data).decode()
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """INSERT INTO matches(match_id, source, date, map_name, avg_elo, avg_elo_bracket, data, last_updated)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(match_id) DO UPDATE SET
                 data=excluded.data, avg_elo=excluded.avg_elo,
                 avg_elo_bracket=excluded.avg_elo_bracket, last_updated=excluded.last_updated""",
            (match_id, source, date, map_name, avg_elo, avg_elo_bracket, payload, now),
        )
        self.conn.commit()

    def get_matches(self, bracket=None, date_from=None, date_to=None, source=None, limit=1000):
        q = "SELECT * FROM matches WHERE 1=1"
        params = []
        if bracket is not None:
            q += " AND avg_elo_bracket=?"
            params.append(bracket)
        if date_from:
            q += " AND date>=?"
            params.append(date_from)
        if date_to:
            q += " AND date<=?"
            params.append(date_to)
        if source:
            q += " AND source=?"
            params.append(source)
        q += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["data"] = orjson.loads(d["data"]) if d["data"] else {}
            out.append(d)
        return out

    def count_matches_by_bracket(self, source="faceit"):
        rows = self.conn.execute(
            "SELECT avg_elo_bracket, COUNT(*) as cnt FROM matches WHERE source=? AND avg_elo_bracket>0 GROUP BY avg_elo_bracket ORDER BY avg_elo_bracket",
            (source,)).fetchall()
        return [dict(r) for r in rows]

    def save_verdict(self, steam_id, probability, reasons, calibrated=False, confidence=0.0):
        self.conn.execute(
            """INSERT INTO cheater_verdicts(steam_id, probability, reasons, calibrated, confidence, updated_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(steam_id) DO UPDATE SET
                 probability=excluded.probability, reasons=excluded.reasons,
                 calibrated=excluded.calibrated, confidence=excluded.confidence,
                 updated_at=excluded.updated_at""",
            (steam_id, probability, orjson.dumps(reasons).decode(),
             int(calibrated), confidence, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def get_verdict(self, steam_id):
        row = self.conn.execute("SELECT * FROM cheater_verdicts WHERE steam_id=?", (steam_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["reasons"] = orjson.loads(d["reasons"]) if d["reasons"] else []
        return d

    def add_calibration_sample(self, steam_id, predicted, actual, features):
        self.conn.execute(
            "INSERT INTO calibration(steam_id, predicted, actual, features, created_at) VALUES(?,?,?,?,?)",
            (steam_id, predicted, actual, orjson.dumps(features).decode(), datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
