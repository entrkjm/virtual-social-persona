"""
New Follower Scenario
새로운 팔로워가 생겼을 때

우선순위 4 - 팔로우백 판단
기존 FollowEngine 로직 통합 (점수 기반 + 지연 큐)
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api.social import NotificationData
from agent.platforms.twitter.api import social as twitter_api
from agent.platforms.twitter.modes.social.follow_engine import FollowEngine, FollowDecision


class NewFollowerScenario(BaseScenario):
    """
    새 팔로워 시나리오

    판단 포인트 (FollowEngine 위임):
    1. 봇인가 진짜 유저인가? (프로필/바이오/팔로워비율 체크)
    2. 관심 분야가 겹치는가? (바이오 키워드 매칭)
    3. 팔로우백 할 것인가? (점수 기반 결정)
    """

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)
        self.follow_engine = FollowEngine()

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

        # 유저 정보 구성 (FollowEngine용)
        user_info = self._build_user_info(data)

        return ScenarioContext(
            person=person,
            post_id=None,
            post_text=None,
            conversation=None,
            extra={
                'notification': data,
                'user_info': user_info
            }
        )

    def _build_user_info(self, data: NotificationData) -> Dict[str, Any]:
        """FollowEngine에 전달할 유저 정보 구성"""
        return {
            'id': data.get('from_user_id', ''),
            'user_id': data.get('from_user_id', ''),
            'screen_name': data.get('from_user', ''),
            'profile_image': data.get('profile_image_url'),
            'bio': data.get('bio', data.get('description', '')),
            'description': data.get('bio', data.get('description', '')),
            'followers_count': data.get('followers_count', 0),
            'following_count': data.get('following_count', data.get('friends_count', 0)),
            'friends_count': data.get('following_count', data.get('friends_count', 0)),
            'following_me': True,  # 팔로우 알림이므로 항상 True
            'created_at': data.get('account_created_at')
        }

    def _judge(self, context: ScenarioContext) -> Dict[str, Any]:
        """FollowEngine 기반 판단"""
        person = context.person
        user_info = context.extra.get('user_info', {})

        # 이미 아는 사람이면 즉시 팔로우백
        if person.tier in ('familiar', 'friend'):
            return {
                'action': 'follow',
                'reason': f'known person ({person.tier})',
                'use_queue': False,
                'score': 100.0
            }

        # FollowEngine으로 판단 위임
        interaction_context = {
            'interaction_count': len(person.latest_conversations) if person.latest_conversations else 0
        }

        follow_decision: FollowDecision = self.follow_engine.should_follow(
            user=user_info,
            interaction_context=interaction_context
        )

        if follow_decision.should_follow:
            return {
                'action': 'follow',
                'reason': follow_decision.reason,
                'use_queue': True,
                'delay_seconds': follow_decision.delay_seconds,
                'score': follow_decision.score
            }

        return {
            'action': 'skip',
            'reason': follow_decision.reason,
            'score': follow_decision.score
        }

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'skip')

        if action != 'follow':
            return ScenarioResult(
                success=True,
                action='skip',
                details={'reason': decision.get('reason'), 'score': decision.get('score')}
            )

        user_id = context.extra.get('notification', {}).get('from_user_id')
        screen_name = context.person.screen_name if context.person else ''

        if not user_id:
            return ScenarioResult(success=False, action='follow', details={'error': 'no user_id'})

        # 지연 큐 사용 여부
        use_queue = decision.get('use_queue', True)

        if use_queue:
            # 지연 큐에 추가 (FollowEngine이 나중에 실행)
            self.follow_engine.queue_follow(
                user_id=user_id,
                screen_name=screen_name,
                context={'scenario': 'new_follower', 'person_tier': context.person.tier if context.person else 'stranger'}
            )
            return ScenarioResult(
                success=True,
                action='follow_queued',
                details={
                    'reason': decision.get('reason'),
                    'score': decision.get('score'),
                    'delay_seconds': decision.get('delay_seconds', 0)
                }
            )
        else:
            # 즉시 실행 (아는 사람)
            success = twitter_api.follow_user(user_id)
            if success:
                self.follow_engine.daily_count += 1
                self.follow_engine.followed_users.add(user_id)

            return ScenarioResult(
                success=success,
                action='follow',
                details={'reason': decision.get('reason'), 'immediate': True}
            )

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if not context.person:
            return

        if result.action in ('follow', 'follow_queued'):
            # 팔로우 또는 큐 등록 시 tier 업그레이드
            if context.person.tier == 'stranger':
                context.person.tier = 'acquaintance'

            self.update_person_after_interaction(
                context.person,
                interaction_type='follow_back'
            )

    def process_follow_queue(self) -> list:
        """
        큐에 있는 팔로우 실행 (외부에서 주기적으로 호출)

        Returns:
            List of (screen_name, success, reason)
        """
        return self.follow_engine.process_queue(twitter_api.follow_user)

    def get_queue_status(self) -> Dict:
        """큐 상태 조회"""
        return self.follow_engine.get_queue_status()
