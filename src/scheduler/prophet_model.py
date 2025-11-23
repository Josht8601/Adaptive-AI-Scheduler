# scheduler/prophet_model.py
from datetime import datetime, timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd
from prophet import Prophet

from .models import UserPrefs, FixedEvent, Task


def _compute_meeting_density(slots_df: pd.DataFrame,
                             fixed_df: pd.DataFrame,
                             window_min: int = 90) -> np.ndarray:
    """Fraction (0..1) of minutes occupied by fixed events in +/- window around each slot."""
    if fixed_df.empty:
        return np.zeros(len(slots_df))

    half = pd.Timedelta(minutes=window_min)
    vals = []
    for t in slots_df["ds"]:
        s, e = t - half, t + half
        overlap_min = 0.0
        for _, r in fixed_df.iterrows():
            st, en = r["start"], r["end"]
            if en <= s or st >= e:
                continue
            overlap_min += (min(en, e) - max(st, s)).total_seconds() / 60.0
        vals.append(overlap_min / (2 * window_min))
    return np.array(vals)


def _add_deadline_pressure(df: pd.DataFrame,
                           tasks_df: pd.DataFrame,
                           window_days: int = 3) -> pd.DataFrame:
    """Max ramp (0..1) across tasks as deadlines approach within window_days."""
    out = df.copy()
    out["deadline_pressure"] = 0.0
    if len(tasks_df):
        for _, t in tasks_df.iterrows():
            ddl = t.get("latest")
            if pd.notnull(ddl):
                ddl = pd.to_datetime(ddl)
                days_left = (ddl - out["ds"]).dt.total_seconds() / 86400
                out["deadline_pressure"] = np.maximum(
                    out["deadline_pressure"],
                    np.clip((window_days - days_left) / window_days, 0, 1),
                )
    return out


def add_regressors(df: pd.DataFrame,
                   prefs: UserPrefs,
                   fixed_df: pd.DataFrame,
                   tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Add preference and context features as Prophet regressors."""
    out = df.copy()
    ds = out["ds"]

    out["prefer_morning"] = (
        (ds.dt.hour >= prefs.prefer_morning_start)
        & (ds.dt.hour <= prefs.prefer_morning_end)
    ).astype(int)

    out["avoid_late"] = (ds.dt.hour >= prefs.avoid_evenings_after).astype(int)
    out["is_weekend"] = (ds.dt.weekday >= 5).astype(int)
    out["meeting_density"] = _compute_meeting_density(out, fixed_df, window_min=90)
    out = _add_deadline_pressure(out, tasks_df, window_days=3)
    return out


def build_slots(week_start: datetime,
                prefs: UserPrefs,
                days: int = 7) -> pd.DataFrame:
    """Create the grid of candidate time slots for the week."""
    week_end = week_start + timedelta(days=days)
    slots = pd.DataFrame({
        "ds": pd.date_range(
            week_start, week_end,
            freq=f"{prefs.slot_minutes}min",
            inclusive="left"
        )
    })
    slots["hour"] = slots["ds"].dt.hour
    slots["weekday"] = slots["ds"].dt.weekday
    slots["is_weekend"] = (slots["weekday"] >= 5).astype(int)
    return slots


def build_history(week_start: datetime,
                  prefs: UserPrefs) -> pd.DataFrame:
    """Build a simple 4-week pseudo-history with priors for Prophet cold-start."""
    hist_start = week_start - timedelta(days=28)
    hist_end = week_start
    hist = pd.DataFrame({
        "ds": pd.date_range(
            hist_start, hist_end,
            freq=f"{prefs.slot_minutes}min",
            inclusive="left"
        )
    })
    hist["hour"] = hist["ds"].dt.hour
    hist["weekday"] = hist["ds"].dt.weekday
    hist["prefer_morning"] = (
        (hist["hour"] >= prefs.prefer_morning_start)
        & (hist["hour"] <= prefs.prefer_morning_end)
    ).astype(int)
    hist["avoid_late"] = (hist["hour"] >= prefs.avoid_evenings_after).astype(int)
    hist["is_weekend"] = (hist["weekday"] >= 5).astype(int)

    # Prior utility ~ 0.65 for morning, 0.45 otherwise, minus penalties
    base = (
        0.45
        + 0.20 * hist["prefer_morning"]
        - 0.15 * hist["avoid_late"]
        - 0.15 * hist["is_weekend"]
    )
    hist["y"] = np.clip(base, 0.05, 0.95)
    return hist


def fit_prophet(hist_reg: pd.DataFrame) -> Prophet:
    """Fit Prophet model on prepared history with regressors."""
    df = hist_reg.copy()
    df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)

    m = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        seasonality_mode="additive",
        uncertainty_samples=0,  # faster, good enough here
    )
    for reg in ["prefer_morning", "avoid_late", "is_weekend",
                "meeting_density", "deadline_pressure"]:
        m.add_regressor(reg)

    m.fit(df.rename(columns={"y": "y"}))
    return m


def score_slots_with_prophet(
    week_start: datetime,
    prefs: UserPrefs,
    fixed_events: List[FixedEvent],
    tasks: List[Task],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build history, fit Prophet, and score slots for the target week.

    Returns:
        slots: dataframe with 'ds', 'hour', 'weekday', 'is_weekend', 'utility_base'
        fixed_df: fixed events dataframe aligned to slots
    """
    # Convert input lists to dataframes for easier handling
    if fixed_events:
        fixed_df = pd.DataFrame([{
            "id": fe.id,
            "label": fe.label,
            "start": fe.start,
            "end": fe.end
        } for fe in fixed_events])
    else:
        fixed_df = pd.DataFrame(columns=["id", "label", "start", "end"])

    if tasks:
        tasks_df = pd.DataFrame([{
            "id": t.id,
            "label": t.label,
            "dur_h": t.dur_h,
            "priority": t.priority,
            "latest": t.latest
        } for t in tasks])
    else:
        tasks_df = pd.DataFrame(columns=[
            "id", "label", "dur_h", "priority", "latest"
        ])

    # Build grids
    slots = build_slots(week_start, prefs)
    hist = build_history(week_start, prefs)

    # Add regressors
    hist_reg = add_regressors(hist[["ds", "y"]].copy(), prefs, fixed_df, tasks_df)
    future_reg = add_regressors(slots[["ds"]].copy(), prefs, fixed_df, tasks_df)

    # Fit & predict
    m = fit_prophet(hist_reg)
    fut = future_reg.copy()
    fut["ds"] = pd.to_datetime(fut["ds"]).dt.tz_localize(None)
    forecast = m.predict(fut)

    slots["utility_base"] = forecast["yhat"].clip(0, 1).values
    return slots, fixed_df
