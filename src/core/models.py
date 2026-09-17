"""Модели данных."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerProfile:
    steam_id: str = ""
    faceit_id: str = ""
    nickname: str = ""
    avatar_url: str = ""
    steam_url: str = ""
    faceit_url: str = ""
    country: str = ""
    faceit_level: int = 0
    faceit_elo: int = 0
    premier_rating: int = 0
    vac_banned: bool = False
    game_banned: bool = False
    cswatch_risk: str = ""
    cswatch_cheater: bool = False
    last_updated: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class MatchPlayerStats:
    steam_id: str
    nickname: str
    team: str = ""
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    kd: float = 0.0
    adr: float = 0.0
    hs_percent: float = 0.0
    rating: float = 0.0
    mvps: int = 0
    first_kills: int = 0
    clutches_won: int = 0
    clutches_lost: int = 0
    entry_success: float = 0.0
    reaction_time_ms: float = 0.0
    preaim: float = 0.0
    elo: int = 0
    faceit_level: int = 0
    party_size: int = 0
    country: str = ""


@dataclass
class CheaterVerdict:
    steam_id: str
    probability: float = 0.0
    reasons: list = field(default_factory=list)
    calibrated: bool = False
    confidence: float = 0.0
