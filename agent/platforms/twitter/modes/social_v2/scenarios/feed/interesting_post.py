"""
Interesting Post Scenario
관심있는 주제의 글을 발견했을 때

HYBRID v1에서 FeedJourney가 rule-based로 선택한 후 실행됨
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext


class InterestingPostScenario(BaseScenario):
    """
    관심 포스트 시나리오

    FeedJourney에서 interesting으로 분류됨 (core_interests 매칭)
    여기서 실제로 어떻게 반응할지 결정
    """

    def execute(self, data: Dict[str, Any]) -> Optional[ScenarioResult]:
        """시나리오 실행"""
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

        if not post_id:
            return None

        person = self.get_person(user_id, screen_name) if user_id else None

        return ScenarioContext(
            person=person,
            post_id=post_id,
            post_text=post_text,
            conversation=None,
            extra={'post': data}
        )

    def _judge(self, context: ScenarioContext) -> Dict[str, Any]:
        """
        판단 로직

        관심 주제이므로 반응 가능성 높음
        TODO: LLM으로 실제 관심도 + 반응 타입 결정
        """
        text = context.post_text or ""
        engagement = context.extra.get('post', {}).get('engagement', {})

        # 인기 포스트면 더 적극적
        likes = engagement.get('favorite_count', 0)
        retweets = engagement.get('retweet_count', 0)
        is_popular = likes > 50 or retweets > 10

        # 질문이면 답글
        if '?' in text:
            return {'action': 'reply', 'reason': 'interesting question'}

        # 인기 포스트면 like
        if is_popular:
            return {'action': 'like', 'reason': 'popular interesting post'}

        # 50% 확률로 like
        import random
        if random.random() < 0.5:
            return {'action': 'like', 'reason': 'interesting topic'}

        return {'action': 'skip', 'reason': 'random skip'}

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
        if context.person and result.action in ('like', 'reply'):
            self.update_person_after_interaction(
                context.person,
                interaction_type=result.action
            )
