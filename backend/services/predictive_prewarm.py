import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("finops.scheduler.predictive")


class PredictivePrewarmEngine:
    """
    Analyzes historical high-frequency time-series telemetry (CPU, RAM, Requests)
    to detect recurring workload diurnal patterns and compute predictive pre-warming schedules.
    """

    IDLE_CPU_THRESHOLD = 15.0       # Below 15% is considered idle/micro-idle
    ACTIVE_REQUESTS_THRESHOLD = 50   # Above 50 requests/min indicates incoming users

    @classmethod
    def generate_demo_telemetry_series(
        cls,
        days: int = 14,
        instance_id: str = "i-0a817b3c4d5e6f001"
    ) -> List[Dict[str, Any]]:
        """
        Generates realistic multi-day high-frequency telemetry exhibiting:
        - Weekday micro-idle overnight (00:00 - 07:30)
        - Activity onset at 07:45 (CPU ramp, user arrivals)
        - Heavy business workload (08:00 - 19:30)
        - Evening ramp-down (19:45 - 20:00)
        - Weekend continuous micro-idle
        """
        series = []
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days)

        current = start_time
        # Generate 15-minute intervals
        while current <= now:
            weekday = current.weekday() # 0 = Monday, 6 = Sunday
            hour = current.hour
            minute = current.minute
            time_decimal = hour + (minute / 60.0)

            is_weekend = weekday >= 5

            if is_weekend:
                # Weekend: Deep idle
                cpu = round(random.uniform(1.2, 4.5), 1)
                mem = round(random.uniform(18.0, 22.0), 1)
                reqs = random.randint(0, 5)
                active_ssh = 0
            else:
                # Weekday lifecycle
                if time_decimal < 7.5:
                    # 00:00 - 07:30: Overnight micro-idle
                    cpu = round(random.uniform(1.5, 4.8), 1)
                    mem = round(random.uniform(19.0, 23.0), 1)
                    reqs = random.randint(0, 10)
                    active_ssh = 0
                elif 7.5 <= time_decimal < 8.0:
                    # 07:30 - 08:00: Pre-workload activity begins at 07:45
                    progress = (time_decimal - 7.5) / 0.5  # 0.0 to 1.0
                    cpu = round(5.0 + progress * 30.0 + random.uniform(-2, 2), 1)
                    mem = round(22.0 + progress * 25.0, 1)
                    reqs = int(10 + progress * 140)
                    active_ssh = 1 if progress > 0.5 else 0
                elif 8.0 <= time_decimal < 19.5:
                    # 08:00 - 19:30: Peak operational workday
                    wave = (math.sin((time_decimal - 8) / 11.5 * math.pi))
                    cpu = round(40.0 + wave * 38.0 + random.uniform(-4, 4), 1)
                    mem = round(50.0 + wave * 22.0 + random.uniform(-2, 2), 1)
                    reqs = int(200 + wave * 350 + random.randint(-30, 30))
                    active_ssh = random.choice([0, 1, 2])
                elif 19.5 <= time_decimal < 20.0:
                    # 19:30 - 20:00: Evening wind-down
                    progress = 1.0 - ((time_decimal - 19.5) / 0.5)
                    cpu = round(4.0 + progress * 35.0, 1)
                    mem = round(20.0 + progress * 28.0, 1)
                    reqs = int(5 + progress * 100)
                    active_ssh = 0
                else:
                    # 20:00 - 23:59: Overnight idle
                    cpu = round(random.uniform(1.5, 4.2), 1)
                    mem = round(random.uniform(18.5, 21.5), 1)
                    reqs = random.randint(0, 8)
                    active_ssh = 0

            series.append({
                "timestamp": current.isoformat(),
                "time_label": current.strftime("%Y-%m-%d %H:%M"),
                "instance_id": instance_id,
                "weekday": weekday,
                "hour": hour,
                "minute": minute,
                "cpu_utilization": max(0.5, min(100.0, cpu)),
                "memory_utilization": max(5.0, min(100.0, mem)),
                "network_requests": max(0, reqs),
                "active_ssh": active_ssh,
            })

            current += timedelta(minutes=15)

        return series

    @classmethod
    def analyze_usage_patterns(
        cls,
        telemetry: List[Dict[str, Any]],
        prewarm_lead_minutes: int = 15
    ) -> Dict[str, Any]:
        """
        Analyzes historical telemetry points to detect:
        1. Onset of daily user activity
        2. Evening closure
        3. Recurrence confidence across days
        4. Calculates pre-warming schedule: (activity_onset - prewarm_lead)
        """
        if not telemetry:
            return {"pattern_detected": False, "confidence": 0.0, "reason": "No telemetry data provided"}

        instance_id = telemetry[0].get("instance_id", "i-unknown")

        # Group by date and find first and last active slots
        daily_activity: Dict[str, Dict[str, Any]] = {}

        for pt in telemetry:
            dt = datetime.fromisoformat(pt["timestamp"].replace("Z", "+00:00"))
            date_key = dt.strftime("%Y-%m-%d")
            weekday = dt.weekday()

            if date_key not in daily_activity:
                daily_activity[date_key] = {
                    "weekday": weekday,
                    "active_slots": [],
                    "idle_slots": []
                }

            is_active = (
                pt.get("cpu_utilization", 0) >= cls.IDLE_CPU_THRESHOLD or
                pt.get("network_requests", 0) >= cls.ACTIVE_REQUESTS_THRESHOLD
            )

            time_str = dt.strftime("%H:%M")
            if is_active:
                daily_activity[date_key]["active_slots"].append(time_str)
            else:
                daily_activity[date_key]["idle_slots"].append(time_str)

        # Analyze weekday patterns vs weekend patterns
        weekday_start_times = []
        weekday_stop_times = []
        weekend_active_days = 0

        for date_key, info in daily_activity.items():
            if info["weekday"] < 5:  # Monday to Friday
                if info["active_slots"]:
                    weekday_start_times.append(info["active_slots"][0])
                    weekday_stop_times.append(info["active_slots"][-1])
            else:
                if len(info["active_slots"]) > 4:
                    weekend_active_days += 1

        if not weekday_start_times:
            return {
                "instance_id": instance_id,
                "pattern_detected": False,
                "confidence": 0.0,
                "reason": "Instance had no sustained active working windows detected in history"
            }

        # Find median/mode start time
        def to_minutes(t_str: str) -> int:
            h, m = map(int, t_str.split(":"))
            return h * 60 + m

        def to_time_str(mins: int) -> str:
            h = (mins // 60) % 24
            m = mins % 60
            return f"{h:02d}:{m:02d}"

        start_mins = sorted([to_minutes(t) for t in weekday_start_times])
        stop_mins = sorted([to_minutes(t) for t in weekday_stop_times])

        median_start = start_mins[len(start_mins) // 2]
        median_stop = stop_mins[len(stop_mins) // 2]

        # Calculate consistency/confidence: percentage of weekdays within +/- 30m of median
        consistent_starts = sum(1 for m in start_mins if abs(m - median_start) <= 30)
        confidence = round(consistent_starts / max(1, len(start_mins)), 2)

        # Pre-warming lead time: start earlier so instance is warm when users arrive
        prewarm_start_mins = max(0, median_start - prewarm_lead_minutes)

        detected_activity_start = to_time_str(median_start)
        recommended_prewarm_start = to_time_str(prewarm_start_mins)
        recommended_stop = to_time_str(median_stop)

        # Calculate estimated savings: 24h - (work hours)
        daily_runtime_hours = (median_stop - prewarm_start_mins) / 60.0
        weekly_runtime_hours = daily_runtime_hours * 5.0
        total_week_hours = 168.0
        savings_percent = round((1.0 - (weekly_runtime_hours / total_week_hours)) * 100, 1)

        return {
            "instance_id": instance_id,
            "pattern_detected": confidence >= 0.70,
            "confidence": confidence,
            "detected_activity_start": detected_activity_start,
            "detected_activity_stop": recommended_stop,
            "recommended_start_time": recommended_prewarm_start,
            "recommended_stop_time": recommended_stop,
            "prewarm_minutes": prewarm_lead_minutes,
            "grace_period_minutes": 10,
            "active_days": {
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False,
            },
            "estimated_savings_percent": savings_percent,
            "reason": (
                f"Diurnal business pattern detected with {int(confidence*100)}% confidence. "
                f"Activity begins recurringly at {detected_activity_start}. "
                f"Predictive Pre-Warming initiates at {recommended_prewarm_start} ({prewarm_lead_minutes}m lead). "
                f"Off-hours shutdown saves ~{savings_percent}% in compute waste."
            )
        }
