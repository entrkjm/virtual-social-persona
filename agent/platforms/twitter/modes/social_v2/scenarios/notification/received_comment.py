"""
Received Comment Scenario
내 글에 누군가 댓글을 달았을 때

가장 높은 우선순위 - 내 컨텐츠에 대한 반응이므로 반드시 확인
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api.social import NotificationData


class ReceivedCommentScenario(BaseScenario):
    """
    내 글에 댓글이 달렸을 때 시나리오

    판단 포인트:
    1. 누가 댓글을 달았는가? (아는 사람 vs 처음 보는 사람)
    2. 어떤 내용인가? (질문 vs 감상 vs 반박)
    3. 대화를 이어갈 것인가? (reply vs like only vs skip)
    """

    def execute(self, data: NotificationData) -> Optional[ScenarioResult]:
        """
        시나리오 실행

        Args:
            data: NotificationData (from_user, tweet_id, tweet_text 등)
        """
        # 1. 컨텍스트 수집
        context = self._gather_context(data)
        if not context:
            return None

        # 2. 판단 (TODO: LLM 연동)
        decision = self._judge(context)

        # 3. 실행
        result = self._execute_action(context, decision)

        # 4. 메모리 업데이트
        if result and result.success:
            self._update_memory(context, result)

        return result

    def _gather_context(self, data: NotificationData) -> Optional[ScenarioContext]:
        """컨텍스트 수집"""
        from_user = data.get('from_user', '')
        from_user_id = data.get('from_user_id', '')
        tweet_id = data.get('tweet_id')
        tweet_text = data.get('tweet_text', '')

        if not from_user or not tweet_id:
            return None

        # PersonMemory 조회/생성
        person = self.get_person(from_user_id, from_user)

        # 대화 기록 조회/생성
        conversation = self.get_or_create_conversation(
            person_id=person.user_id,
            post_id=tweet_id,
            conversation_type='my_post_reply'
        )

        return ScenarioContext(
            person=person,
            post_id=tweet_id,
            post_text=tweet_text,
            conversation=conversation,
            extra={'notification': data}
        )

    def _judge(self, context: ScenarioContext) -> Dict[str, Any]:
        """
        판단 로직

        TODO: LLM 연동하여 실제 판단
        현재는 기본 로직으로 구현
        """
        person = context.person
        text = context.post_text or ""

        # 기본 판단: 아는 사람이면 reply, 아니면 like
        if person.tier in ('familiar', 'friend'):
            return {
                'action': 'reply',
                'reason': f'familiar person ({person.tier})',
                'reply_type': 'normal'
            }

        # 질문이면 reply
        if '?' in text or '어떻게' in text or '뭐' in text:
            return {
                'action': 'reply',
                'reason': 'question detected',
                'reply_type': 'answer'
            }

        # 기본: like만
        return {
            'action': 'like',
            'reason': 'default response'
        }

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'skip')

        if action == 'skip':
            return ScenarioResult(success=True, action='skip')

        if action == 'like':
            # TODO: 실제 like API 호출
            return ScenarioResult(
                success=True,
                action='like',
                details={'reason': decision.get('reason')}
            )

        if action == 'reply':
            # TODO: LLM으로 답글 생성 + API 호출
            return ScenarioResult(
                success=True,
                action='reply',
                content="[답글 생성 예정]",
                details={
                    'reason': decision.get('reason'),
                    'reply_type': decision.get('reply_type')
                }
            )

        return None

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if not context.person:
            return

        # PersonMemory 업데이트
        self.update_person_after_interaction(
            context.person,
            interaction_type=result.action,
            summary=f"Replied to my post: {context.post_text[:50]}..."
        )

        # Conversation 업데이트
        if context.conversation and result.action == 'reply':
            self.update_conversation_after_turn(
                context.conversation,
                summary=f"I replied to their comment",
                is_concluded=False
            )
