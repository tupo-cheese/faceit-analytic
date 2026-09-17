"""Базовый источник данных."""
from abc import ABC, abstractmethod


class DataSource(ABC):
    name = "base"

    @abstractmethod
    async def fetch_player(self, steam_id):
        ...

    @abstractmethod
    async def fetch_matches(self, steam_id, limit=50):
        ...

    async def close(self):
        pass
