"""
Quoted Scenario
누군가 내 글을 인용했을 때

우선순위 3 - 내 컨텐츠 확산이므로 확인
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.platforms.twitter.api.social import NotificationData


class QuotedScenario(BaseScenario):
    """
    인용 시나리오

    판단 포인트:
    1. 긍정적 인용인가 부정적 인용인가?
    2. 대화에 참여할 필요가 있는가?
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
                conversation_type='quote'
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

        # 아는 사람이면 reply로 감사 표현
        if person.tier in ('familiar', 'friend'):
            return {'action': 'reply', 'reason': 'thank familiar person'}

        # 기본: like (인용 자체를 인정)
        return {'action': 'like', 'reason': 'acknowledge quote'}

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'like')

        if action == 'reply':
            return ScenarioResult(
                success=True,
                action='reply',
                content="[감사 답글 예정]"
            )

        return ScenarioResult(success=True, action='like')

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if context.person:
            self.update_person_after_interaction(
                context.person,
                interaction_type=result.action
            )
