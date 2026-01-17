"""
Mode Manager
AGENT_MODE 기반 설정 오버라이드
normal | test | aggressive
"""
import os
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal
from enum import Enum


class AgentMode(str, Enum):
    NORMAL = "normal"
    TEST = "test"
    AGGRESSIVE = "aggressive"


@dataclass
class ModeConfig:
    step_interval_min: int
    step_interval_max: int
    like_probability: float
    comment_probability: float
    repost_probability: float
    warmup_steps: int
    sleep_enabled: bool
    random_breaks: bool


MODE_CONFIGS: Dict[AgentMode, ModeConfig] = {
    AgentMode.NORMAL: ModeConfig(
        step_interval_min=60,
        step_interval_max=180,
        like_probability=0.25,
        comment_probability=0.08,
        repost_probability=0.05,
        warmup_steps=5,
        sleep_enabled=True,
        random_breaks=True
    ),
    AgentMode.TEST: ModeConfig(
        step_interval_min=15,
        step_interval_max=45,
        like_probability=0.40,
        comment_probability=0.15,
        repost_probability=0.10,
        warmup_steps=2,
        sleep_enabled=False,
        random_breaks=False
    ),
    AgentMode.AGGRESSIVE: ModeConfig(
        step_interval_min=8,
        step_interval_max=20,
        like_probability=0.60,
        comment_probability=0.25,
        repost_probability=0.15,
        warmup_steps=0,
        sleep_enabled=False,
        random_breaks=False
    )
}


class ModeManager:
    def __init__(self, mode: str = None):
        mode_str = mode or os.getenv("AGENT_MODE", "normal")
        try:
            self.mode = AgentMode(mode_str.lower())
        except ValueError:
            print(f"[MODE] Invalid mode '{mode_str}', falling back to normal")
            self.mode = AgentMode.NORMAL

        self._original_mode = self.mode
        self._consecutive_errors = 0
        self._error_226_count = 0
        self._daily_action_count = 0
        self._max_daily_actions = 200

    @property
    def config(self) -> ModeConfig:
        return MODE_CONFIGS[self.mode]

    def get_config_override(self) -> Dict[str, Any]:
        cfg = self.config
        return {
            "step_interval": {
                "min": cfg.step_interval_min,
                "max": cfg.step_interval_max
            },
            "like_probability": cfg.like_probability,
            "comment_probability": cfg.comment_probability,
            "repost_probability": cfg.repost_probability,
            "warmup_steps": cfg.warmup_steps,
            "sleep_enabled": cfg.sleep_enabled,
            "random_breaks": cfg.random_breaks
        }

    def apply_to_behavior(self, behavior_config: Dict) -> Dict:
        """behavior 설정에 모드 오버라이드 적용

        Args:
            behavior_config: 기존 behavior 설정 dict

        Returns:
            모드가 적용된 behavior 설정
        """
        cfg = self.config
        result = dict(behavior_config) if behavior_config else {}

        if "interaction_patterns" not in result:
            result["interaction_patterns"] = {}

        result["interaction_patterns"]["independent_actions"] = {
            "like_probability": cfg.like_probability,
            "comment_probability": cfg.comment_probability,
            "repost_probability": cfg.repost_probability
        }

        return result

    def get_step_interval(self) -> tuple[int, int]:
        cfg = self.config
        return cfg.step_interval_min, cfg.step_interval_max

    def should_warmup(self, current_step: int) -> bool:
        return current_step < self.config.warmup_steps

    def should_sleep(self) -> bool:
        return self.config.sleep_enabled

    def should_take_break(self) -> bool:
        return self.config.random_breaks

    def on_error(self, error_code: Optional[int] = None):
        """에러 발생 시 호출

        Args:
            error_code: HTTP 에러 코드 (226 = rate limit)
        """
        self._consecutive_errors += 1

        if error_code == 226:
            self._error_226_count += 1
            if self.mode == AgentMode.AGGRESSIVE:
                print(f"[MODE] Error 226 detected in aggressive mode, switching to normal")
                self._switch_to_normal()

        if self._consecutive_errors >= 3:
            print(f"[MODE] 3 consecutive errors, switching to normal and pausing")
            self._switch_to_normal()
            return True

        return False

    def on_success(self):
        """성공 시 호출 - 에러 카운터 리셋"""
        self._consecutive_errors = 0
        self._daily_action_count += 1

    def _switch_to_normal(self):
        """안전모드로 전환"""
        if self.mode != AgentMode.NORMAL:
            print(f"[MODE] Switching from {self.mode.value} to normal")
            self.mode = AgentMode.NORMAL

    def restore_original_mode(self):
        """원래 모드로 복원 (에러 해소 후)"""
        if self.mode != self._original_mode:
            print(f"[MODE] Restoring to {self._original_mode.value}")
            self.mode = self._original_mode

    def is_daily_limit_reached(self) -> bool:
        return self._daily_action_count >= self._max_daily_actions

    def reset_daily_counters(self):
        """일일 카운터 리셋"""
        self._daily_action_count = 0
        self._error_226_count = 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "original_mode": self._original_mode.value,
            "consecutive_errors": self._consecutive_errors,
            "error_226_count": self._error_226_count,
            "daily_action_count": self._daily_action_count,
            "daily_limit_reached": self.is_daily_limit_reached()
        }


mode_manager = ModeManager()
