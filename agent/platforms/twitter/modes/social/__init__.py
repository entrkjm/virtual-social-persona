"""
Social Mode v2
Notification-centric, scenario-based social interaction

HYBRID v1: Rule-based classification → 1 post selection → LLM judgment
TODO(v2): Per-post individual LLM judgment
"""
from .engine import SocialEngineV2
from .journeys.base import JourneyResult
from .scenarios.base import ScenarioResult

__all__ = ['SocialEngineV2', 'JourneyResult', 'ScenarioResult']
