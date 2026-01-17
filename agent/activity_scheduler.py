"""
Activity Scheduler
페르소나별 휴식/활동 스케줄 관리
"""
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum


class ActivityState(Enum):
    ACTIVE = "active"
    SLEEPING = "sleeping"
    BREAK = "break"
    OFF_DAY = "off_day"


@dataclass
class DailySchedule:
    date: str
    sleep_start: int
    wake_time: int
    is_off_day: bool = False
    breaks: list = field(default_factory=list)
    midnight_check_time: Optional[int] = None


class ActivityScheduler:

    def __init__(self, behavior_config: Dict):
        self.config = behavior_config.get('activity_schedule', {})
        self._today_schedule: Optional[DailySchedule] = None
        self._break_until: Optional[datetime] = None

    def _get_sleep_config(self) -> Dict:
        return self.config.get('sleep_pattern', {
            'base_sleep_start': 1,
            'base_wake_time': 7,
            'variance': {'sleep_start': 2, 'wake_time': 1.5},
            'exceptions': {
                'late_night_probability': 0.15,
                'early_wake_probability': 0.10,
                'midnight_check_probability': 0.08
            },
            'weekend_modifier': {'sleep_start': 1, 'wake_time': 2}
        })

    def _get_hourly_activity(self) -> Dict[str, float]:
        return self.config.get('hourly_activity', {
            "07-09": 0.3,
            "09-12": 0.7,
            "12-14": 0.5,
            "14-18": 0.8,
            "18-22": 1.0,
            "22-01": 0.6
        })

    def _get_break_config(self) -> Dict:
        return self.config.get('random_breaks', {
            'enabled': True,
            'probability': 0.15,
            'duration_min': 30,
            'duration_max': 180
        })

    def _get_off_day_config(self) -> Dict:
        return self.config.get('random_off_day', {
            'enabled': True,
            'probability': 0.10
        })

    def _is_weekend(self, dt: Optional[datetime] = None) -> bool:
        if dt is None:
            dt = datetime.now()
        return dt.weekday() >= 5

    def get_todays_schedule(self) -> DailySchedule:
        today = datetime.now().strftime('%Y-%m-%d')

        if self._today_schedule and self._today_schedule.date == today:
            return self._today_schedule

        sleep_config = self._get_sleep_config()
        off_day_config = self._get_off_day_config()

        is_off_day = False
        if off_day_config.get('enabled', True):
            if random.random() < off_day_config.get('probability', 0.10):
                is_off_day = True

        base_sleep_start = sleep_config.get('base_sleep_start', 1)
        base_wake_time = sleep_config.get('base_wake_time', 7)
        variance = sleep_config.get('variance', {})
        exceptions = sleep_config.get('exceptions', {})
        weekend_mod = sleep_config.get('weekend_modifier', {})

        sleep_variance = variance.get('sleep_start', 2)
        wake_variance = variance.get('wake_time', 1.5)

        sleep_start = base_sleep_start + random.uniform(-sleep_variance/2, sleep_variance/2)
        wake_time = base_wake_time + random.uniform(-wake_variance/2, wake_variance/2)

        if self._is_weekend():
            sleep_start += weekend_mod.get('sleep_start', 1)
            wake_time += weekend_mod.get('wake_time', 2)

        if random.random() < exceptions.get('late_night_probability', 0.15):
            sleep_start += random.uniform(1, 3)

        if random.random() < exceptions.get('early_wake_probability', 0.10):
            wake_time -= random.uniform(0.5, 1.5)

        midnight_check = None
        if random.random() < exceptions.get('midnight_check_probability', 0.08):
            midnight_check = random.randint(2, 5)

        sleep_start = max(0, min(sleep_start, 5))
        wake_time = max(5, min(wake_time, 12))

        self._today_schedule = DailySchedule(
            date=today,
            sleep_start=int(sleep_start),
            wake_time=int(wake_time),
            is_off_day=is_off_day,
            midnight_check_time=midnight_check
        )

        return self._today_schedule

    def _is_sleeping(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.now()

        schedule = self.get_todays_schedule()
        hour = now.hour

        if schedule.midnight_check_time and hour == schedule.midnight_check_time:
            return False

        if schedule.sleep_start <= 5:
            if hour >= schedule.sleep_start and hour < schedule.wake_time:
                return True
        else:
            if hour >= schedule.sleep_start or hour < schedule.wake_time:
                return True

        return False

    def is_active_now(self) -> Tuple[bool, ActivityState, Optional[datetime]]:
        """
        현재 활동 가능한지 확인
        Returns: (is_active, state, next_active_time)
        """
        now = datetime.now()
        schedule = self.get_todays_schedule()

        if schedule.is_off_day:
            tomorrow = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
            return False, ActivityState.OFF_DAY, tomorrow

        if self._break_until and now < self._break_until:
            return False, ActivityState.BREAK, self._break_until

        if self._is_sleeping(now):
            wake_time = now.replace(
                hour=schedule.wake_time,
                minute=random.randint(0, 30),
                second=0
            )
            if now.hour < schedule.wake_time:
                pass
            else:
                wake_time += timedelta(days=1)
            return False, ActivityState.SLEEPING, wake_time

        return True, ActivityState.ACTIVE, None

    def get_activity_level(self) -> float:
        """현재 활동 강도 (0-1)"""
        is_active, state, _ = self.is_active_now()
        if not is_active:
            return 0.0

        now = datetime.now()
        hour = now.hour
        hourly_activity = self._get_hourly_activity()

        for time_range, level in hourly_activity.items():
            try:
                start, end = time_range.split('-')
                start_hour = int(start)
                end_hour = int(end)

                if end_hour < start_hour:
                    if hour >= start_hour or hour < end_hour:
                        return level
                else:
                    if start_hour <= hour < end_hour:
                        return level
            except ValueError:
                continue

        return 0.5

    def should_take_break(self) -> bool:
        """랜덤 휴식 발생 여부"""
        break_config = self._get_break_config()

        if not break_config.get('enabled', True):
            return False

        if self._break_until and datetime.now() < self._break_until:
            return False

        if random.random() < break_config.get('probability', 0.15):
            duration_min = break_config.get('duration_min', 30)
            duration_max = break_config.get('duration_max', 180)
            duration = random.randint(duration_min, duration_max)
            self._break_until = datetime.now() + timedelta(minutes=duration)
            return True

        return False

    def get_seconds_until_active(self) -> int:
        """다음 활성 시간까지 초"""
        is_active, _, next_active = self.is_active_now()

        if is_active:
            return 0

        if next_active:
            delta = next_active - datetime.now()
            return max(0, int(delta.total_seconds()))

        return 3600

    def get_status_summary(self) -> Dict:
        """현재 상태 요약"""
        is_active, state, next_active = self.is_active_now()
        schedule = self.get_todays_schedule()

        return {
            'is_active': is_active,
            'state': state.value,
            'activity_level': self.get_activity_level(),
            'next_active_time': next_active.isoformat() if next_active else None,
            'todays_schedule': {
                'date': schedule.date,
                'sleep_start': schedule.sleep_start,
                'wake_time': schedule.wake_time,
                'is_off_day': schedule.is_off_day,
                'midnight_check': schedule.midnight_check_time
            }
        }
