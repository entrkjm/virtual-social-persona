"""
New Follower Scenario
새로운 팔로워가 생겼을 때

우선순위 4 - 팔로우백 판단
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.platforms.twitter.api.social import NotificationData


class NewFollowerScenario(BaseScenario):
    """
    새 팔로워 시나리오

    판단 포인트:
    1. 봇인가 진짜 유저인가?
    2. 관심 분야가 겹치는가?
    3. 팔로우백 할 것인가?
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

        if not from_user:
            return None

        person = self.get_person(from_user_id, from_user)

        return ScenarioContext(
            person=person,
            post_id=None,
            post_text=None,
            conversation=None,
            extra={'notification': data}
        )

    def _judge(self, context: ScenarioContext) -> Dict[str, Any]:
        """판단 로직 (TODO: 프로필 분석)"""
        person = context.person

        # 이미 아는 사람이면 팔로우백
        if person.tier != 'stranger':
            return {'action': 'follow', 'reason': 'known person'}

        # TODO: 프로필/바이오 분석하여 봇 여부, 관심사 매칭 판단
        # 현재는 기본적으로 skip (나중에 LLM으로 판단)
        return {'action': 'skip', 'reason': 'need profile analysis'}

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'skip')

        if action == 'follow':
            # TODO: 실제 follow API 호출
            return ScenarioResult(
                success=True,
                action='follow',
                details={'reason': decision.get('reason')}
            )

        return ScenarioResult(success=True, action='skip')

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if context.person and result.action == 'follow':
            context.person.tier = 'acquaintance'
            self.update_person_after_interaction(
                context.person,
                interaction_type='follow_back'
            )
