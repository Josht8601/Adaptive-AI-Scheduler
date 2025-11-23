# scheduler/scheduler.py
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd

from .models import UserPrefs, FixedEvent, Task
from .prophet_model import score_slots_with_prophet
from .optimizer import optimize_schedule


def generate_schedule(week_start: datetime,
                      prefs: UserPrefs,
                      fixed_events: List[FixedEvent],
                      tasks: List[Task],
                      missed_intervals: Optional[List[Tuple[pd.Timestamp, pd.Timestamp]]] = None,
                      start_from: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """
    Generate a weekly schedule.

    missed_intervals: list of (start, end) ranges that should not be reused.
    start_from: earliest datetime that tasks are allowed to be scheduled at.
                Any slots before this time will be treated as blocked.
    """
    # Sanity: ensure week_start is tz-aware
    if week_start.tzinfo is None:
        raise ValueError("week_start must be timezone-aware")

    # 1) Get Prophet-based utility scores per slot
    slots, fixed_df = score_slots_with_prophet(
        week_start=week_start,
        prefs=prefs,
        fixed_events=fixed_events,
        tasks=tasks,
    )

    # 2) Run optimization to assign tasks to slots
    scheduled_df = optimize_schedule(
        slots=slots,
        tasks=tasks,
        prefs=prefs,
        fixed_df=fixed_df,
        missed_intervals=missed_intervals or [],
        start_from=start_from, 
    )

    return scheduled_df, slots
