"""
Follow Action
팔로우 실행
"""
from typing import Optional

from .base import BaseAction, ActionResult
from agent.platforms.twitter.api import social as twitter_api


class FollowAction(BaseAction):
    """팔로우 액션"""

    def execute(self, user_id: str, **kwargs) -> ActionResult:
        """
        팔로우 실행

        Args:
            user_id: 팔로우할 유저 ID
        """
        if not self.can_execute(user_id=user_id):
            return ActionResult(
                success=False,
                action_type='follow',
                error='Cannot execute: missing user_id'
            )

        try:
            success = twitter_api.follow_user(user_id)
            return ActionResult(
                success=success,
                action_type='follow',
                target_id=user_id
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='follow',
                target_id=user_id,
                error=str(e)
            )

    def can_execute(self, user_id: Optional[str] = None, **kwargs) -> bool:
        """실행 가능 여부"""
        return bool(user_id)
