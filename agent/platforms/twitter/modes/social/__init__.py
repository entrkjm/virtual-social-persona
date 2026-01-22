"""
Social Mode
Notification-centric, scenario-based social interaction

Rule-based classification → 1 post selection → LLM judgment
"""
from .engine import SocialEngine
from .journeys.base import JourneyResult
from .scenarios.base import ScenarioResult

__all__ = ['SocialEngine', 'JourneyResult', 'ScenarioResult']
