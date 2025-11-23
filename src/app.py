import os
import csv
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from streamlit_calendar import calendar

from scheduler.models import UserPrefs, FixedEvent, Task
from scheduler.scheduler import generate_schedule

from prometheus_client import start_http_server, Summary, Counter
import time


# ✅ Create metric only once
if "SCHEDULE_TIME" not in st.session_state:
    st.session_state.SCHEDULE_TIME = Summary(
        "schedule_generation_seconds",
        "Time spent generating weekly AI schedule",
    )
SCHEDULE_TIME = st.session_state.SCHEDULE_TIME

# ✅ Create feedback counter only once
if "FEEDBACK_COUNTER" not in st.session_state:
    st.session_state.FEEDBACK_COUNTER = Counter(
        "schedule_feedback_total",
        "Count of feedback submissions by rating",
        ["rating"],  # label = rating 1–5
    )
FEEDBACK_COUNTER = st.session_state.FEEDBACK_COUNTER


# ✅ Start metrics server only once
if "metrics_started" not in st.session_state:
    start_http_server(8000)
    st.session_state.metrics_started = True


def datetime_input(label: str, key: str):
    """
    Replacement for st.datetime_input using date_input + time_input.
    Returns a naive datetime (no timezone).
    """
    col_date, col_time = st.columns(2)
    with col_date:
        d = st.date_input(label + " date", key=key + "_date")
    with col_time:
        t = st.time_input(label + " time", key=key + "_time")
    return datetime.combine(d, t)

# Session State Setup
if "fixed_events" not in st.session_state:
    st.session_state.fixed_events = []  # list[FixedEvent]

if "tasks" not in st.session_state:
    st.session_state.tasks = []         # list[Task]

if "prefs" not in st.session_state:
    st.session_state.prefs = UserPrefs()

if "week_start" not in st.session_state:
    # default: next Monday local
    today = pd.Timestamp.now(tz=st.session_state.prefs.tz)
    monday = today - pd.Timedelta(days=today.weekday())  # this Monday
    st.session_state.week_start = monday.normalize()

if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = pd.DataFrame(
        columns=["id", "label", "start", "end", "priority"]
    )

if "slots" not in st.session_state:
    st.session_state.slots = pd.DataFrame()

if "missed_intervals" not in st.session_state:
    st.session_state.missed_intervals = []  # list of (start,end)


# Sidebar: Inputs
st.sidebar.title("AI Scheduling Assistant")

# Week selector
st.sidebar.subheader("Week")
week_date = st.sidebar.date_input(
    "Week of (Monday)",
    value=st.session_state.week_start.date()
)
# update stored week_start (tz-aware)
st.session_state.week_start = pd.Timestamp(
    datetime.combine(week_date, datetime.min.time())
).tz_localize(st.session_state.prefs.tz)

# Preferences
st.sidebar.subheader("Preferences")
pm_start = st.sidebar.number_input("Morning start hour", 0, 23,
                                   value=st.session_state.prefs.prefer_morning_start)
pm_end = st.sidebar.number_input("Morning end hour", 0, 23,
                                 value=st.session_state.prefs.prefer_morning_end)
avoid_after = st.sidebar.number_input("Avoid scheduling after", 0, 23,
                                      value=st.session_state.prefs.avoid_evenings_after)
weekend_ok = st.sidebar.checkbox("Allow weekends?", value=st.session_state.prefs.weekend_ok)
slot_minutes = st.sidebar.selectbox("Slot size (minutes)", [30, 60],
                                    index=1 if st.session_state.prefs.slot_minutes == 60 else 0)

st.session_state.prefs.prefer_morning_start = int(pm_start)
st.session_state.prefs.prefer_morning_end = int(pm_end)
st.session_state.prefs.avoid_evenings_after = int(avoid_after)
st.session_state.prefs.weekend_ok = weekend_ok
st.session_state.prefs.slot_minutes = int(slot_minutes)

# Add Fixed Event
st.sidebar.subheader("Add Fixed Event")
with st.sidebar.form("fixed_form"):
    fe_label = st.text_input("Label", key="fe_label")
    fe_start = datetime_input("Start", key="fe_start")
    fe_end = datetime_input("End", key="fe_end")
    add_fixed = st.form_submit_button("Add Fixed Event")
    if add_fixed:
        if fe_label and fe_end > fe_start:
            TZ = st.session_state.prefs.tz
            st.session_state.fixed_events.append(
                FixedEvent(
                    id=f"fe{len(st.session_state.fixed_events)}",
                    label=fe_label,
                    start=pd.Timestamp(fe_start).tz_localize(TZ),
                    end=pd.Timestamp(fe_end).tz_localize(TZ),
                )
            )
        else:
            st.sidebar.error("Please enter a label and ensure end > start")

# Add Dynamic Task
st.sidebar.subheader("Add Dynamic Task")
with st.sidebar.form("task_form"):
    t_label = st.text_input("Task label", key="t_label")
    t_dur = st.number_input("Duration (hours)", min_value=0.5, max_value=8.0, step=0.5, value=1.0)
    t_priority = st.slider("Priority (1 low, 3 high)", 1, 3, 2)
    t_deadline_enable = st.checkbox("Has deadline?", key="t_deadline_enable")
    t_deadline = datetime_input("Deadline", key="t_deadline") if t_deadline_enable else None
    add_task = st.form_submit_button("Add Task")
    if add_task:
        if t_label:
            TZ = st.session_state.prefs.tz
            latest_ts = pd.Timestamp(t_deadline).tz_localize(TZ) if t_deadline else None
            st.session_state.tasks.append(
                Task(
                    id=f"t{len(st.session_state.tasks)}",
                    label=t_label,
                    dur_h=float(t_dur),
                    priority=int(t_priority),
                    latest=latest_ts,
                )
            )
        else:
            st.sidebar.error("Please enter a task label.")


# Main: Generate Schedule
st.title("Weekly AI Calendar")

col1, col2 = st.columns(2)
with col1:
    st.markdown("### Current Fixed Events")
    if st.session_state.fixed_events:
        fedf = pd.DataFrame([{
            "label": fe.label,
            "start": fe.start,
            "end": fe.end,
        } for fe in st.session_state.fixed_events])
        st.dataframe(fedf)
    else:
        st.write("No fixed events yet.")

with col2:
    st.markdown("### Current Dynamic Tasks")
    if st.session_state.tasks:
        tdf = pd.DataFrame([{
            "id": t.id,
            "label": t.label,
            "dur_h": t.dur_h,
            "priority": t.priority,
            "latest": t.latest,
        } for t in st.session_state.tasks])
        st.dataframe(tdf)
    else:
        st.write("No tasks yet.")


if st.button("Generate Schedule"):
    st.session_state.missed_intervals = []  # reset misses on fresh plan

    TZ = st.session_state.prefs.tz
    week_start = st.session_state.week_start
    week_end = week_start + pd.Timedelta(days=7)
    now = pd.Timestamp.now(tz=TZ)

    # Earliest allowed scheduling time
    if week_start <= now <= week_end:
        # Same week as “today” → don’t schedule in the past
        # Round down to the nearest slot boundary
        minutes = st.session_state.prefs.slot_minutes
        minute_floor = (now.minute // minutes) * minutes
        start_from = now.replace(minute=minute_floor, second=0, microsecond=0)
    elif now < week_start:
        # Week in the future → okay to schedule from week_start
        start_from = week_start
    else:
        # Week entirely in the past → allow full week (or you could block entirely)
        start_from = week_start

    with SCHEDULE_TIME.time():
        scheduled_df, slots = generate_schedule(
            week_start=week_start,
            prefs=st.session_state.prefs,
            fixed_events=st.session_state.fixed_events,
            tasks=st.session_state.tasks,
            missed_intervals=st.session_state.missed_intervals,
            start_from=start_from,     # 👈 NEW
        )

    st.session_state.schedule_df = scheduled_df
    st.session_state.slots = slots



# Real Calendar UI with FullCalendar
if not st.session_state.schedule_df.empty:
    st.markdown("## Weekly Calendar View")

    # Build events for FullCalendar
    def priority_color(p):
        if p >= 3:
            return "#d62728"  # red
        if p == 2:
            return "#1f77b4"  # blue
        return "#2ca02c"      # green

    events = []
    for _, row in st.session_state.schedule_df.iterrows():
        events.append({
            "title": row["label"],
            "start": pd.Timestamp(row["start"]).isoformat(),
            "end": pd.Timestamp(row["end"]).isoformat(),
            "id": row["id"],
            "color": priority_color(row["priority"]),
        })

    # Optionally show fixed events as separate color
    for fe in st.session_state.fixed_events:
        events.append({
            "title": fe.label,
            "start": fe.start.isoformat(),
            "end": fe.end.isoformat(),
            "id": fe.id,
            "color": "#7f7f7f",  # grey
        })

    cal_options = {
        "initialView": "timeGridWeek",
        "slotMinTime": "06:00:00",
        "slotMaxTime": "23:00:00",
        "allDaySlot": False,
        "nowIndicator": True,
        "weekNumbers": False,
        "firstDay": 1,  # Monday
    }

    calendar(events=events, options=cal_options, key="calendar")

    # Utility plot for transparency
    if not st.session_state.slots.empty:
        st.markdown("### Predicted Slot Utility")
        fig = px.line(st.session_state.slots, x="ds", y="utility_base",
                      labels={"ds": "Time", "utility_base": "Utility"})
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Add some events/tasks and click **Generate Schedule** to see the calendar.")


# Missed Task → Reschedule
st.markdown("---")
st.markdown("### Missed a dynamic event?")

if not st.session_state.schedule_df.empty:
    # Only dynamic (task) IDs, not fixed events
    dynamic_ids = {t.id for t in st.session_state.tasks}
    sched_dyn = st.session_state.schedule_df[
        st.session_state.schedule_df["id"].isin(dynamic_ids)
    ]

    if not sched_dyn.empty:
        sel = st.selectbox(
            "Select the event you missed:",
            options=list(sched_dyn.index),
            format_func=lambda idx: f'{sched_dyn.loc[idx, "label"]} ({sched_dyn.loc[idx, "start"]})'
        )

        if st.button("Mark as missed and reschedule"):
            missed_row = sched_dyn.loc[sel]
            start_missed = pd.Timestamp(missed_row["start"])
            end_missed = pd.Timestamp(missed_row["end"])

            # Add missed interval so optimizer avoids that block next time
            st.session_state.missed_intervals.append((start_missed, end_missed))

            # Determine earliest allowed time
            TZ = st.session_state.prefs.tz
            week_start = st.session_state.week_start
            week_end = week_start + pd.Timedelta(days=7)
            now = pd.Timestamp.now(tz=TZ)

            if week_start <= now <= week_end:
                # Same week as today — block earlier slots
                minutes = st.session_state.prefs.slot_minutes
                minute_floor = (now.minute // minutes) * minutes
                start_from = now.replace(minute=minute_floor, second=0, microsecond=0)
            elif now < week_start:
                # Week in future
                start_from = week_start
            else:
                # Week in past
                start_from = week_start

            # Re-run schedule with updated missed_intervals
            scheduled_df, slots = generate_schedule(
                week_start=week_start,
                prefs=st.session_state.prefs,
                fixed_events=st.session_state.fixed_events,
                tasks=st.session_state.tasks,
                missed_intervals=st.session_state.missed_intervals,
                start_from=start_from,   # 👈 NEW
            )

            st.session_state.schedule_df = scheduled_df
            st.session_state.slots = slots

            st.success("Schedule updated to account for the missed event.")

    else:
        st.write("No dynamic scheduled events to mark as missed.")
else:
    st.write("Generate a schedule first.")


st.markdown("---")
st.markdown("### Feedback on the AI scheduler")

st.write(
    "Rate how useful this schedule was for you and, if you want, leave a short comment. "
    "This feedback helps improve future versions of the assistant."
)

with st.form("feedback_form"):
    rating = st.slider(
        "Overall, how satisfied are you with this schedule?",
        min_value=1,
        max_value=5,
        value=4,
        help="1 = very dissatisfied, 5 = very satisfied",
    )
    comment = st.text_area(
        "Optional: What worked well or what should be improved?",
        ""
    )
    submitted = st.form_submit_button("Submit feedback")

if submitted:
    tz = st.session_state.prefs.tz
    ts = pd.Timestamp.now(tz=tz)

    log_path = "feedback_log.csv"
    row = {
        "timestamp": ts.isoformat(),
        "rating": int(rating),
        "comment": comment.replace("\n", " "),
    }

    file_exists = os.path.isfile(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    FEEDBACK_COUNTER.labels(rating=rating).inc()

    st.success("Thank you for your feedback!")