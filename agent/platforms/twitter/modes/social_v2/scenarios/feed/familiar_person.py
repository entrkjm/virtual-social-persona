"""
Familiar Person Scenario
아는 사람의 글을 발견했을 때

HYBRID v1에서 FeedJourney가 rule-based로 선택한 후 실행됨
"""
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase, PersonMemory
from agent.platforms.twitter.api import social as twitter_api
from ...judgment import EngagementJudge, ReplyGenerator


class FamiliarPersonScenario(BaseScenario):
    """
    아는 사람 글 시나리오

    이미 FeedJourney에서 familiar로 분류된 상태
    여기서는 실제 반응 결정 + 실행
    """

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)
        self.judge = EngagementJudge()
        self.reply_gen = ReplyGenerator(persona_config)

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
        """LLM 기반 판단"""
        result = self.judge.judge(
            post_text=context.post_text or "",
            person=context.person,
            scenario_type='familiar_person_post',
            extra_context=None
        )

        return {
            'action': result.action,
            'reason': result.reason,
            'reply_type': result.reply_type or 'normal',
            'confidence': result.confidence
        }

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'skip')
        tweet_id = context.post_id

        if action == 'skip':
            return ScenarioResult(success=True, action='skip')

        if action == 'like':
            success = twitter_api.like_tweet(tweet_id)
            return ScenarioResult(success=success, action='like')

        if action == 'reply':
            reply_content = self.reply_gen.generate(
                post_text=context.post_text or "",
                person=context.person,
                reply_type=decision.get('reply_type', 'normal')
            )

            if not reply_content:
                # 답글 실패 시 like로 폴백
                success = twitter_api.like_tweet(tweet_id)
                return ScenarioResult(success=success, action='like')

            result = twitter_api.reply_to_tweet(tweet_id, reply_content)
            success = result is not None

            # reply 성공 시 like도 함께
            if success:
                twitter_api.like_tweet(tweet_id)

            return ScenarioResult(
                success=success,
                action='reply',
                content=reply_content,
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
