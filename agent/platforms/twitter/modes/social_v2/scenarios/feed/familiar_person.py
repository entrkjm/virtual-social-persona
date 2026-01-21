"""
Familiar Person Scenario
아는 사람의 글을 발견했을 때

HYBRID v1에서 FeedJourney가 rule-based로 선택한 후 실행됨
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import PersonMemory


class FamiliarPersonScenario(BaseScenario):
    """
    아는 사람 글 시나리오

    이미 FeedJourney에서 familiar로 분류된 상태
    여기서는 실제 반응 결정 + 실행
    """

    def execute(self, data: Dict[str, Any]) -> Optional[ScenarioResult]:
        """
        시나리오 실행

        Args:
            data: 포스트 데이터 (FeedJourney에서 전달)
        """
        context = self._gather_context(data)
        if not context:
            return None

        decision = self._judge(context)
        result = self._execute_action(context, decision)

        if result and result.success:
            self._update_memory(context, result)

        return result

    def _gather_context(self, data: Dict[str, Any]) -> Optional[ScenarioContext]:
        """컨텍스트 수집"""
        user_id = data.get('user_id') or data.get('user', '')
        screen_name = data.get('user', '')
        post_id = data.get('id')
        post_text = data.get('text', '')

        if not user_id or not post_id:
            return None

        person = self.get_person(user_id, screen_name)

        conversation = self.get_or_create_conversation(
            person_id=person.user_id,
            post_id=post_id,
            conversation_type='their_post_reply'
        )

        return ScenarioContext(
            person=person,
            post_id=post_id,
            post_text=post_text,
            conversation=conversation,
            extra={'post': data}
        )

    def _judge(self, context: ScenarioContext) -> Dict[str, Any]:
        """
        판단 로직

        아는 사람이므로 기본적으로 적극 반응
        TODO: LLM으로 답글 내용 결정
        """
        person = context.person
        text = context.post_text or ""

        # friend 티어면 거의 항상 반응
        if person.tier == 'friend':
            if '?' in text:
                return {'action': 'reply', 'reason': 'friend asked question'}
            return {'action': 'like', 'reason': 'friend post'}

        # familiar 티어
        if '?' in text:
            return {'action': 'reply', 'reason': 'familiar asked question'}

        # 70% 확률로 like
        import random
        if random.random() < 0.7:
            return {'action': 'like', 'reason': 'familiar post'}

        return {'action': 'skip', 'reason': 'random skip'}

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'skip')

        if action == 'like':
            # TODO: 실제 like API 호출
            return ScenarioResult(success=True, action='like')

        if action == 'reply':
            # TODO: LLM으로 답글 생성 + API 호출
            return ScenarioResult(
                success=True,
                action='reply',
                content="[답글 생성 예정]",
                details={'reason': decision.get('reason')}
            )

        return ScenarioResult(success=True, action='skip')

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if context.person and result.action in ('like', 'reply'):
            self.update_person_after_interaction(
                context.person,
                interaction_type=result.action
            )

            if context.conversation and result.action == 'reply':
                self.update_conversation_after_turn(
                    context.conversation,
                    summary=f"Replied to their post"
                )
