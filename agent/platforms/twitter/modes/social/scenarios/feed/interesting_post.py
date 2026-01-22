"""
Interesting Post Scenario
관심있는 주제의 글을 발견했을 때

HYBRID v1에서 FeedJourney가 rule-based로 선택한 후 실행됨
"""
import logging
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api import social as twitter_api
from ...judgment import EngagementJudge, ReplyGenerator

logger = logging.getLogger("agent")


class InterestingPostScenario(BaseScenario):
    """
    관심 포스트 시나리오

    FeedJourney에서 interesting으로 분류됨 (core_interests 매칭)
    여기서 실제로 어떻게 반응할지 결정
    """

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)
        self.judge = EngagementJudge()
        self.reply_gen = ReplyGenerator(persona_config)

    def execute(self, data: Dict[str, Any]) -> Optional[ScenarioResult]:
        """시나리오 실행"""
        logger.info(f"[Scenario:InterestingPost] Starting for @{data.get('user')}")
        
        context = self._gather_context(data)
        if not context:
            logger.warning("[Scenario:InterestingPost] Failed to gather context")
            return None

        logger.debug(f"[Scenario:InterestingPost] Context: post_id={context.post_id}, person_tier={context.person.tier if context.person else 'N/A'}")
        
        decision = self._judge(context)
        logger.info(f"[Scenario:InterestingPost] Judge decision: action={decision.get('action')}, confidence={decision.get('confidence')}, reason={decision.get('reason')}")
        
        result = self._execute_action(context, decision)
        logger.info(f"[Scenario:InterestingPost] Result: success={result.success if result else False}, action={result.action if result else 'none'}")

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
        """LLM 기반 판단"""
        result = self.judge.judge(
            post_text=context.post_text or "",
            person=context.person,
            scenario_type='interesting_post',
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
            logger.debug(f"[Scenario:InterestingPost] Action: skip")
            return ScenarioResult(success=True, action='skip')

        if action == 'like':
            logger.info(f"[Scenario:InterestingPost] Action: like tweet_id={tweet_id}")
            success = twitter_api.like_tweet(tweet_id)
            logger.info(f"[Scenario:InterestingPost] Like result: {success}")
            return ScenarioResult(success=success, action='like')

        if action == 'reply':
            logger.info(f"[Scenario:InterestingPost] Action: reply (type={decision.get('reply_type', 'normal')})")
            reply_content = self.reply_gen.generate(
                post_text=context.post_text or "",
                person=context.person,
                reply_type=decision.get('reply_type', 'normal')
            )

            if not reply_content:
                logger.warning("[Scenario:InterestingPost] Reply generation failed, falling back to like")
                success = twitter_api.like_tweet(tweet_id)
                return ScenarioResult(success=success, action='like')

            logger.info(f"[Scenario:InterestingPost] Reply content: {reply_content[:50]}...")
            result = twitter_api.reply_to_tweet(tweet_id, reply_content)
            success = result is not None
            logger.info(f"[Scenario:InterestingPost] Reply result: {success}")

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
