# scheduler/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UserPrefs:
    tz: str = "America/New_York"
    slot_minutes: int = 60
    avoid_evenings_after: int = 20  # 24h
    prefer_morning_start: int = 8
    prefer_morning_end: int = 11
    weekend_ok: bool = False
    buffer_minutes: int = 60        # gap between tasks
    max_hours_per_day: int = 4      # cap scheduled hours/day


@dataclass
class FixedEvent:
    id: str
    label: str
    start: datetime  # tz-aware
    end: datetime    # tz-aware


@dataclass
class Task:
    id: str
    label: str
    dur_h: float
    priority: int
    latest: Optional[datetime] = None  # tz-aware or None
