"""
Quoted Scenario
누군가 내 글을 인용했을 때

우선순위 3 - 내 컨텐츠 확산이므로 확인
"""
import logging
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api.social import NotificationData
from agent.platforms.twitter.api import social as twitter_api
from ...judgment import EngagementJudge, ReplyGenerator

logger = logging.getLogger("agent")


class QuotedScenario(BaseScenario):
    """
    인용 시나리오

    판단 포인트:
    1. 긍정적 인용인가 부정적 인용인가?
    2. 대화에 참여할 필요가 있는가?
    """

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)
        self.judge = EngagementJudge()
        self.reply_gen = ReplyGenerator(persona_config)

    def execute(self, data: NotificationData) -> Optional[ScenarioResult]:
        """시나리오 실행"""
        logger.info(f"[Scenario:Quoted] Starting for @{data.get('from_user')}")
        
        context = self._gather_context(data)
        if not context:
            logger.warning("[Scenario:Quoted] Failed to gather context")
            return None

        decision = self._judge(context)
        logger.info(f"[Scenario:Quoted] Judge decision: action={decision.get('action')}, confidence={decision.get('confidence')}")
        
        result = self._execute_action(context, decision)
        logger.info(f"[Scenario:Quoted] Result: success={result.success if result else False}, action={result.action if result else 'none'}")

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
        """LLM 기반 판단"""
        result = self.judge.judge(
            post_text=context.post_text or "",
            person=context.person,
            scenario_type='quote',
            extra_context=None
        )

        return {
            'action': result.action,
            'reason': result.reason,
            'reply_type': result.reply_type or 'short',
            'confidence': result.confidence
        }

    def _execute_action(
        self, context: ScenarioContext, decision: Dict[str, Any]
    ) -> Optional[ScenarioResult]:
        """액션 실행"""
        action = decision.get('action', 'like')
        tweet_id = context.post_id

        if action == 'skip':
            return ScenarioResult(success=True, action='skip')

        if action == 'like' and tweet_id:
            success = twitter_api.like_tweet(tweet_id)
            return ScenarioResult(success=success, action='like')

        if action == 'reply' and tweet_id:
            recent_replies = self.get_recent_replies(limit=5)
            reply_content = self.reply_gen.generate(
                post_text=context.post_text or "",
                person=context.person,
                reply_type='short',
                recent_replies=recent_replies
            )

            if not reply_content:
                # 답글 생성 실패 시 like로 폴백
                success = twitter_api.like_tweet(tweet_id)
                return ScenarioResult(success=success, action='like')

            result = twitter_api.reply_to_tweet(tweet_id, reply_content)
            return ScenarioResult(
                success=result is not None,
                action='reply',
                content=reply_content
            )

        return ScenarioResult(success=True, action='like')

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        if context.person:
            self.update_person_after_interaction(
                context.person,
                interaction_type=result.action
            )
