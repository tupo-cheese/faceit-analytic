"""Сервис матчей."""
from src.core.database import Database


class MatchService:
    def __init__(self, db):
        self.db = db

    def list_matches(self, source="faceit", limit=50):
        return self.db.get_matches(source=source, limit=limit)

    def count_by_bracket(self, source="faceit"):
        return self.db.count_matches_by_bracket(source)
