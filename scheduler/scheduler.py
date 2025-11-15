# scheduler/scheduler.py
from datetime import datetime
from typing import List

import pandas as pd

from .models import UserPrefs, FixedEvent, Task
from .prophet_model import score_slots_with_prophet
from .optimizer import optimize_schedule


def generate_schedule(week_start: datetime,
                      prefs: UserPrefs,
                      fixed_events: List[FixedEvent],
                      tasks: List[Task]) -> pd.DataFrame:
    """
    Top-level function to generate a weekly schedule.

    Args:
        week_start: tz-aware datetime for the start of the week (e.g., Monday 00:00).
        prefs: User preferences.
        fixed_events: list of FixedEvent (non-movable).
        tasks: list of Task (movable).

    Returns:
        scheduled_df: dataframe with columns [id, label, start, end, priority]
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
    )

    return scheduled_df, slots
