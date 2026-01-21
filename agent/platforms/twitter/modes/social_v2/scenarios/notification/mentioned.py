"""
Mentioned Scenario
누군가 나를 멘션했을 때

우선순위 2 - 직접적인 호출이므로 확인 필요
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api.social import NotificationData


class MentionedScenario(BaseScenario):
    """
    멘션 시나리오

    판단 포인트:
    1. 누가 멘션했는가?
    2. 어떤 맥락인가? (질문, 소개, 태그만)
    3. 대화에 참여할 것인가?
    """

    def execute(self, data: NotificationData) -> Optional[ScenarioResult]:
        """시나리오 실행"""
        context = self._gather_context(data)
        if not context:
            return None

        decision = self._judge(context)
        result = self._execute_action(context, decision)

        if result and result.success:
            self._update_memory(context, result)

        return result

    def _gather_context(self, data: NotificationData) -> Optional[ScenarioContext]:
        """컨텍스트 수집"""
        from_user = data.get('from_user', '')
        from_user_id = data.get('from_user_id', '')
        tweet_id = data.get('tweet_id')
        tweet_text = data.get('tweet_text', '')

        if not from_user:
            return None

        person = self.get_person(from_user_id, from_user)

        conversation = None
        if tweet_id:
            conversation = self.get_or_create_conversation(
                person_id=person.user_id,
                post_id=tweet_id,
                conversation_type='mention'
            )

        return ScenarioContext(
            person=person,
            post_id=tweet_id,
            post_text=tweet_text,
            conversation=conversation,
            extra={'notification': data}
        )

    def _judge(self, context: ScenarioContext) -> Dict[str, Any]:
        """판단 로직"""
        person = context.person
        text = context.post_text or ""

        # 아는 사람이면 reply
        if person.tier in ('familiar', 'friend'):
            return {'action': 'reply', 'reason': 'familiar person'}

        # 질문이면 reply
        if '?' in text:
            return {'action': 'reply', 'reason': 'question'}

        # 기본: like
        return {'action': 'like', 'reason': 'default'}

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'skip')

        if action == 'like':
            return ScenarioResult(success=True, action='like')

        if action == 'reply':
            return ScenarioResult(
                success=True,
                action='reply',
                content="[답글 생성 예정]",
                details={'reason': decision.get('reason')}
            )

        return ScenarioResult(success=True, action='skip')

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if context.person:
            self.update_person_after_interaction(
                context.person,
                interaction_type=result.action
            )
