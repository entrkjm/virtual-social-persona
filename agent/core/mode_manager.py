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
    warmup_steps: int
    sleep_enabled: bool
    random_breaks: bool
    # step 확률 (scout + mentions + post = 1.0)
    # None = 페르소나 값 사용, 값 지정 = 오버라이드
    scout_probability: Optional[float] = None
    mentions_probability: Optional[float] = None
    post_probability: Optional[float] = None
    # action 확률 (Optional - None이면 페르소나 값 사용)
    like_probability: Optional[float] = None
    repost_probability: Optional[float] = None
    comment_probability: Optional[float] = None


MODE_CONFIGS: Dict[AgentMode, ModeConfig] = {
    # normal: 페르소나 설정 그대로 사용 (프로덕션)
    AgentMode.NORMAL: ModeConfig(
        step_interval_min=60,
        step_interval_max=180,
        warmup_steps=5,
        sleep_enabled=True,
        random_breaks=True
        # step 확률 None → 페르소나 값 사용
        # action 확률 None → 페르소나 값 사용
    ),
    # test: 중간 속도, 확률 오버라이드 (테스트)
    AgentMode.TEST: ModeConfig(
        step_interval_min=15,
        step_interval_max=45,
        warmup_steps=2,
        sleep_enabled=False,
        random_breaks=False,
        scout_probability=0.75,
        mentions_probability=0.15,
        post_probability=0.10,
        like_probability=0.45,
        repost_probability=0.45,
        comment_probability=0.12
    ),
    # aggressive: 빠른 속도, 높은 확률 (개발)
    # like = repost > comment >> post
    AgentMode.AGGRESSIVE: ModeConfig(
        step_interval_min=8,
        step_interval_max=20,
        warmup_steps=0,
        sleep_enabled=False,
        random_breaks=False,
        scout_probability=0.99,
        mentions_probability=0.01,
        post_probability=0.01,
        like_probability=0.60,
        repost_probability=0.60,
        comment_probability=0.18
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

    def should_override_probabilities(self) -> bool:
        """확률 오버라이드 여부 (normal이면 페르소나 값 사용)"""
        return self.mode != AgentMode.NORMAL

    def get_config_override(self) -> Dict[str, Any]:
        cfg = self.config
        result = {
            "step_interval": {
                "min": cfg.step_interval_min,
                "max": cfg.step_interval_max
            },
            "warmup_steps": cfg.warmup_steps,
            "sleep_enabled": cfg.sleep_enabled,
            "random_breaks": cfg.random_breaks
        }
        # 확률은 오버라이드 모드일 때만 포함
        if self.should_override_probabilities():
            result["like_probability"] = cfg.like_probability
            result["comment_probability"] = cfg.comment_probability
            result["repost_probability"] = cfg.repost_probability
        return result

    def apply_to_behavior(self, behavior_config: Dict) -> Dict:
        """behavior 설정에 모드 오버라이드 적용 (test/aggressive만)"""
        cfg = self.config
        result = dict(behavior_config) if behavior_config else {}

        # normal 모드면 확률 오버라이드 안 함
        if not self.should_override_probabilities():
            return result

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

    def get_step_probabilities(self, behavior_config: Dict) -> Dict[str, float]:
        """Get step probabilities (override or persona default)
        
        Args:
            behavior_config: Persona behavior configuration
            
        Returns:
            Dict with 'scout', 'mentions', 'post' probabilities
        """
        cfg = self.config
        
        # If mode has overrides, use them
        if cfg.scout_probability is not None:
            return {
                'scout': cfg.scout_probability,
                'mentions': cfg.mentions_probability,
                'post': cfg.post_probability
            }
        
        # Otherwise use persona values
        step_probs = behavior_config.get('step_probabilities', {})
        return {
            'scout': step_probs.get('scout_probability', 0.80),
            'mentions': step_probs.get('mentions_probability', 0.15),
            'reply_check': step_probs.get('reply_check_probability', 0.05), # New
            'post': step_probs.get('post_probability', 0.05) # Reduced in practice as sum > 1 is handled by weights
        }

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
