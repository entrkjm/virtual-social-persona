"""
Reposted Scenario
누군가 내 글을 리포스트(리트윗)했을 때

우선순위 10 (낮음) - 관계 기록용, 직접 반응 불필요
"""
import logging
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api.social import NotificationData

logger = logging.getLogger("agent")


class RepostedScenario(BaseScenario):
    """
    리포스트 시나리오

    리포스트는 직접 반응하기 어려움 (원본은 내 글)
    관계 기록 + PersonMemory 업데이트에 집중
    """

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)

    def execute(self, data: NotificationData) -> Optional[ScenarioResult]:
        """시나리오 실행"""
        from_user = data.get('from_user', '')
        logger.info(f"[Scenario:Reposted] @{from_user} reposted my content")

        context = self._gather_context(data)
        if not context:
            logger.warning("[Scenario:Reposted] Failed to gather context")
            return None

        self._update_memory(context)

        return ScenarioResult(
            success=True,
            action='acknowledged',
            details={'from_user': from_user, 'type': 'repost'}
        )

    def _gather_context(self, data: NotificationData) -> Optional[ScenarioContext]:
        """컨텍스트 수집"""
        from_user = data.get('from_user', '')
        from_user_id = data.get('from_user_id', '')
        tweet_id = data.get('tweet_id')
        tweet_text = data.get('tweet_text', '')

        if not from_user:
            return None

        person = self.get_person(from_user_id, from_user)

        return ScenarioContext(
            person=person,
            post_id=tweet_id,
            post_text=tweet_text,
            conversation=None,
            extra={'notification': data}
        )

    def _update_memory(self, context: ScenarioContext):
        """메모리 업데이트 - 리포스트는 긍정적 상호작용"""
        if context.person:
            self.update_person_after_interaction(
                context.person,
                interaction_type='repost_received'
            )
