# demo.py
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

from scheduler.models import UserPrefs, FixedEvent, Task
from scheduler.scheduler import generate_schedule


def main():
    TZ = "America/New_York"

    # Week start (tz-aware)
    week_start = pd.Timestamp("2025-11-03 00:00").tz_localize(TZ)

    prefs = UserPrefs(
        tz=TZ,
        slot_minutes=60,
        avoid_evenings_after=20,
        prefer_morning_start=8,
        prefer_morning_end=11,
        weekend_ok=False,
        buffer_minutes=60,
        max_hours_per_day=4,
    )

    fixed_events = [
        FixedEvent(
            id="class-os",
            label="OS Class",
            start=pd.Timestamp("2025-11-03 12:50").tz_localize(TZ),
            end=pd.Timestamp("2025-11-03 14:45").tz_localize(TZ),
        ),
        FixedEvent(
            id="team-sync",
            label="Team Sync",
            start=pd.Timestamp("2025-11-04 18:30").tz_localize(TZ),
            end=pd.Timestamp("2025-11-04 19:30").tz_localize(TZ),
        ),
        FixedEvent(
            id="iprd",
            label="Profs Mtg",
            start=pd.Timestamp("2025-11-06 13:00").tz_localize(TZ),
            end=pd.Timestamp("2025-11-06 14:30").tz_localize(TZ),
        ),
    ]

    tasks = [
        Task(
            id="dw1",
            label="Deep Work: Project",
            dur_h=3,
            priority=3,
            latest=pd.Timestamp("2025-11-07 17:00").tz_localize(TZ),
        ),
        Task(
            id="study1",
            label="Study: OS",
            dur_h=2,
            priority=2,
            latest=pd.Timestamp("2025-11-08 23:59").tz_localize(TZ),
        ),
        Task(
            id="gym",
            label="Gym",
            dur_h=1,
            priority=1,
            latest=None,
        ),
    ]

    scheduled_df, slots = generate_schedule(
        week_start=week_start,
        prefs=prefs,
        fixed_events=fixed_events,
        tasks=tasks,
    )

    print("=== Schedule ===")
    print(scheduled_df)

    # Plot utility curve
    plt.figure(figsize=(10, 3))
    plt.plot(slots["ds"], slots["utility_base"])
    plt.title("Predicted Slot Utility")
    plt.xlabel("Time")
    plt.ylabel("Utility")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
