"""
Like Action
좋아요 실행
"""
from typing import Optional

from .base import BaseAction, ActionResult
from agent.platforms.twitter.api import social as twitter_api


class LikeAction(BaseAction):
    """좋아요 액션"""

    def execute(self, tweet_id: str, **kwargs) -> ActionResult:
        """
        좋아요 실행

        Args:
            tweet_id: 좋아요할 트윗 ID
        """
        if not self.can_execute(tweet_id=tweet_id):
            return ActionResult(
                success=False,
                action_type='like',
                error='Cannot execute: missing tweet_id'
            )

        try:
            success = twitter_api.like_tweet(tweet_id)
            return ActionResult(
                success=success,
                action_type='like',
                target_id=tweet_id
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='like',
                target_id=tweet_id,
                error=str(e)
            )

    def can_execute(self, tweet_id: Optional[str] = None, **kwargs) -> bool:
        """실행 가능 여부"""
        return bool(tweet_id)
