"""
Reply Action
답글 실행
"""
from typing import Optional

from .base import BaseAction, ActionResult
from agent.platforms.twitter.api import social as twitter_api


class ReplyAction(BaseAction):
    """답글 액션"""

    def execute(
        self,
        tweet_id: str,
        content: str,
        **kwargs
    ) -> ActionResult:
        """
        답글 실행

        Args:
            tweet_id: 답글 대상 트윗 ID
            content: 답글 내용
        """
        if not self.can_execute(tweet_id=tweet_id, content=content):
            return ActionResult(
                success=False,
                action_type='reply',
                error='Cannot execute: missing tweet_id or content'
            )

        try:
            result = twitter_api.reply_to_tweet(tweet_id, content)
            success = result is not None
            return ActionResult(
                success=success,
                action_type='reply',
                target_id=tweet_id,
                content=content
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='reply',
                target_id=tweet_id,
                content=content,
                error=str(e)
            )

    def can_execute(
        self,
        tweet_id: Optional[str] = None,
        content: Optional[str] = None,
        **kwargs
    ) -> bool:
        """실행 가능 여부"""
        return bool(tweet_id) and bool(content)
