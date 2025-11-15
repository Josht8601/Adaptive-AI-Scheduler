# scheduler/optimizer.py
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd
from ortools.sat.python import cp_model

from .models import UserPrefs, Task
# fixed events are already handled when building 'blocked' in scheduler.py


def build_blocked_mask(slots: pd.DataFrame, fixed_df: pd.DataFrame, prefs: UserPrefs,
                       missed_intervals: List[Tuple[pd.Timestamp, pd.Timestamp]],
                       start_from: Optional[pd.Timestamp],) -> np.ndarray:

    blocked = np.zeros(len(slots), dtype=bool)

    if start_from is not None:
        blocked |= (slots["ds"] < start_from).values

    if not fixed_df.empty:
        for _, r in fixed_df.iterrows():
            mask = (slots["ds"] >= r["start"]) & (slots["ds"] < r["end"])
            blocked |= mask.values

    if not prefs.weekend_ok:
        blocked |= (slots["is_weekend"] == 1).values

    # missed intervals (don’t reuse these times)
    for s, e in missed_intervals:
        mask = (slots["ds"] >= s) & (slots["ds"] < e)
        blocked |= mask.values

    return blocked


def feasible_starts(task_row: pd.Series,
                    slots: pd.DataFrame,
                    blocked_mask: np.ndarray,
                    prefs: UserPrefs) -> List[int]:
    dur_slots = int(task_row.dur_h * 60 // prefs.slot_minutes)
    cand = []
    for i in range(len(slots) - dur_slots + 1):
        # any blocked inside?
        if blocked_mask[i:i + dur_slots].any():
            continue
        # deadline check (end <= latest) if provided
        if pd.notnull(task_row.latest):
            end_time = slots.loc[i + dur_slots - 1, "ds"] + pd.Timedelta(
                minutes=prefs.slot_minutes
            )
            if end_time > task_row.latest:
                continue
        cand.append(i)
    return cand


def task_slot_utility(task_row: pd.Series, slot_row: pd.Series) -> float:
    """
    Simple per-task utility adjustment on top of Prophet's base utility.
    Modify this if you want sharper behavior.
    """
    u = float(slot_row.utility_base)
    label = str(task_row.label).lower()
    hour = int(slot_row.hour)

    # Deep work prefers daytime
    if "deep work" in label and not (8 <= hour <= 17):
        u *= 0.85

    # Gym prefers morning
    if "gym" in label:
        u *= 1.3 if 6 <= hour <= 9 else 0.8

    return max(0.0, min(1.0, u))


def optimize_schedule(
    slots: pd.DataFrame,
    tasks: List[Task],
    prefs: UserPrefs,
    fixed_df: pd.DataFrame,
    missed_intervals: List[Tuple[pd.Timestamp, pd.Timestamp]],
    start_from: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    Run CP-SAT to place tasks into slots.

    Returns:
        scheduled_df with columns: id, label, start, end, priority
    """
    # Convert tasks to dataframe for easier indexing
    if tasks:
        tasks_df = pd.DataFrame([{
            "id": t.id,
            "label": t.label,
            "dur_h": t.dur_h,
            "priority": t.priority,
            "latest": t.latest
        } for t in tasks])
    else:
        tasks_df = pd.DataFrame(columns=["id", "label", "dur_h", "priority", "latest"])

    blocked = build_blocked_mask(slots, fixed_df, prefs, missed_intervals, start_from)
    slot_minutes = prefs.slot_minutes

    model = cp_model.CpModel()
    x: Dict[Tuple[int, int], cp_model.IntVar] = {}  # (task_index, start_idx) -> Bool

    dur_slots_list: List[int] = []
    feasible_by_task: List[List[int]] = []

    # Build feasible starts
    for t_idx, task_row in tasks_df.iterrows():
        dur_slots = int(task_row.dur_h * 60 // slot_minutes)
        dur_slots_list.append(dur_slots)
        cand = feasible_starts(task_row, slots, blocked, prefs)
        feasible_by_task.append(cand)
        for i in cand:
            x[(t_idx, i)] = model.NewBoolVar(f"x_t{t_idx}_i{i}")

    # Each task starts exactly once (if feasible)
    for t_idx, _ in tasks_df.iterrows():
        cand = feasible_by_task[t_idx]
        if cand:
            model.Add(sum(x[(t_idx, i)] for i in cand) == 1)

    # No overlaps
    for s in range(len(slots)):
        covers = []
        for t_idx, _ in tasks_df.iterrows():
            dur = dur_slots_list[t_idx]
            for i in feasible_by_task[t_idx]:
                if i <= s < i + dur:
                    covers.append(x[(t_idx, i)])
        if covers:
            model.Add(sum(covers) <= 1)

    # Buffer between tasks
    buffer_slots = prefs.buffer_minutes // slot_minutes
    for t1_idx, _ in tasks_df.iterrows():
        dur1 = dur_slots_list[t1_idx]
        for t2_idx, _ in tasks_df.iterrows():
            if t1_idx >= t2_idx:
                continue
            dur2 = dur_slots_list[t2_idx]
            for i in feasible_by_task[t1_idx]:
                for j in feasible_by_task[t2_idx]:
                    # too close = not (completely separate + buffer)
                    too_close = not (
                        j >= i + dur1 + buffer_slots
                        or i >= j + dur2 + buffer_slots
                    )
                    if too_close:
                        model.AddBoolOr([
                            x[(t1_idx, i)].Not(),
                            x[(t2_idx, j)].Not()
                        ])

    # Daily cap (approx): limit number of task-blocks touching a day
    if prefs.max_hours_per_day > 0:
        max_slots_per_day = prefs.max_hours_per_day * (60 // slot_minutes)
        slot_dates = slots["ds"].dt.date.values
        for d in np.unique(slot_dates):
            starts_touching_day = []
            for t_idx, _ in tasks_df.iterrows():
                dur = dur_slots_list[t_idx]
                for i in feasible_by_task[t_idx]:
                    if any(slots.iloc[i + k]["ds"].date() == d for k in range(dur)):
                        starts_touching_day.append(x[(t_idx, i)])
            if starts_touching_day:
                model.Add(sum(starts_touching_day) <= max_slots_per_day)

    # Objective: maximize total (utility × priority)
    objective_terms = []
    for t_idx, task_row in tasks_df.iterrows():
        dur = dur_slots_list[t_idx]
        for i in feasible_by_task[t_idx]:
            u_block = 0.0
            for k in range(dur):
                u_block += task_slot_utility(task_row, slots.iloc[i + k])
            objective_terms.append(u_block * float(task_row.priority) * x[(t_idx, i)])

    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    _ = solver.Solve(model)

    # Extract schedule
    scheduled = []
    for t_idx, task_row in tasks_df.iterrows():
        dur = dur_slots_list[t_idx]
        for i in feasible_by_task[t_idx]:
            if (t_idx, i) in x and solver.Value(x[(t_idx, i)]) == 1:
                start = slots.loc[i, "ds"]
                end = (
                    slots.loc[i + dur - 1, "ds"]
                    + pd.Timedelta(minutes=slot_minutes)
                )
                scheduled.append((
                    task_row.id,
                    task_row.label,
                    start,
                    end,
                    task_row.priority,
                ))
                break

    scheduled_df = pd.DataFrame(
        scheduled, columns=["id", "label", "start", "end", "priority"]
    ).sort_values("start")
    return scheduled_df
