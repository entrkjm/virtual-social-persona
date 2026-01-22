"""
Received Comment Scenario
내 글에 누군가 댓글을 달았을 때

가장 높은 우선순위 - 내 컨텐츠에 대한 반응이므로 반드시 확인
"""
import logging
from typing import Optional, Dict, Any

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api.social import NotificationData
from agent.platforms.twitter.api import social as twitter_api
from ...judgment import EngagementJudge, ReplyGenerator

logger = logging.getLogger("agent")


class ReceivedCommentScenario(BaseScenario):
    """
    내 글에 댓글이 달렸을 때 시나리오

    판단 포인트:
    1. 누가 댓글을 달았는가? (아는 사람 vs 처음 보는 사람)
    2. 어떤 내용인가? (질문 vs 감상 vs 반박)
    3. 대화를 이어갈 것인가? (reply vs like only vs skip)
    """

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)
        self.judge = EngagementJudge()
        self.reply_gen = ReplyGenerator(persona_config)

    def execute(self, data: NotificationData) -> Optional[ScenarioResult]:
        """
        시나리오 실행

        Args:
            data: NotificationData (from_user, tweet_id, tweet_text 등)
        """
        logger.info(f"[Scenario:ReceivedComment] Starting for @{data.get('from_user')}")
        
        # 1. 컨텍스트 수집
        context = self._gather_context(data)
        if not context:
            logger.warning("[Scenario:ReceivedComment] Failed to gather context")
            return None

        logger.debug(f"[Scenario:ReceivedComment] Context: tweet_id={context.post_id}, person_tier={context.person.tier if context.person else 'N/A'}")

        # 2. 판단
        decision = self._judge(context)
        logger.info(f"[Scenario:ReceivedComment] Judge decision: action={decision.get('action')}, confidence={decision.get('confidence')}, reason={decision.get('reason')}")

        # 3. 실행
        result = self._execute_action(context, decision)
        logger.info(f"[Scenario:ReceivedComment] Result: success={result.success if result else False}, action={result.action if result else 'none'}")

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
        """LLM 기반 판단"""
        result = self.judge.judge(
            post_text=context.post_text or "",
            person=context.person,
            scenario_type='notification_reply',
            extra_context={'is_reply_to_me': True}
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
        """액션 실행 - 실제 API 호출"""
        action = decision.get('action', 'skip')
        tweet_id = context.post_id

        if action == 'skip':
            logger.debug("[Scenario:ReceivedComment] Action: skip")
            return ScenarioResult(success=True, action='skip')

        if action == 'like':
            logger.info(f"[Scenario:ReceivedComment] Action: like tweet_id={tweet_id}")
            success = twitter_api.like_tweet(tweet_id)
            logger.info(f"[Scenario:ReceivedComment] Like result: {success}")
            return ScenarioResult(
                success=success,
                action='like',
                details={'reason': decision.get('reason')}
            )

        if action == 'reply':
            logger.info(f"[Scenario:ReceivedComment] Action: reply (type={decision.get('reply_type', 'normal')})")
            reply_content = self.reply_gen.generate(
                post_text=context.post_text or "",
                person=context.person,
                reply_type=decision.get('reply_type', 'normal'),
                context={'is_reply_to_me': True}
            )

            if not reply_content:
                logger.warning("[Scenario:ReceivedComment] Reply generation failed")
                return ScenarioResult(success=False, action='reply', details={'error': 'empty reply'})

            logger.info(f"[Scenario:ReceivedComment] Reply content: {reply_content[:50]}...")
            result = twitter_api.reply_to_tweet(tweet_id, reply_content)
            success = result is not None
            logger.info(f"[Scenario:ReceivedComment] Reply result: {success}")

            return ScenarioResult(
                success=success,
                action='reply',
                content=reply_content,
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
