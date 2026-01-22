"""
Familiar Person Scenario
아는 사람의 글을 발견했을 때

HYBRID v1에서 FeedJourney가 rule-based로 선택한 후 실행됨
"""
import logging
from typing import Optional, Dict, Any, List

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase, PersonMemory
from agent.platforms.twitter.api import social as twitter_api
from ...judgment import EngagementJudge, ReplyGenerator
from ...judgment.engagement_judge import JudgmentResult

logger = logging.getLogger("agent")


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
        logger.info(f"[Scenario:FamiliarPerson] Starting for @{data.get('user')}")

        context = self._gather_context(data)
        if not context:
            logger.warning("[Scenario:FamiliarPerson] Failed to gather context")
            return None

        logger.debug(f"[Scenario:FamiliarPerson] Context: person_tier={context.person.tier if context.person else 'N/A'}")

        judgment = self._judge(context)
        logger.info(f"[Scenario:FamiliarPerson] Judge: like={judgment.like}, repost={judgment.repost}, reply={judgment.reply}")

        result = self._execute_actions(context, judgment)
        logger.info(f"[Scenario:FamiliarPerson] Result: success={result.success if result else False}, actions={result.details.get('actions') if result else 'none'}")

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

    def _judge(self, context: ScenarioContext) -> JudgmentResult:
        """LLM 기반 판단 - 독립적 액션"""
        extra_context = {}
        post_data = context.extra.get('post', {}) if context.extra else {}

        # replies
        if post_data.get('replies'):
            extra_context['replies'] = post_data['replies']

        # author_profile
        if post_data.get('author_profile'):
            extra_context['author_profile'] = post_data['author_profile']

        return self.judge.judge(
            post_text=context.post_text or "",
            person=context.person,
            scenario_type='familiar_person_post',
            extra_context=extra_context if extra_context else None
        )

    def _execute_actions(
        self, context: ScenarioContext, judgment: JudgmentResult
    ) -> Optional[ScenarioResult]:
        """독립적 액션들 실행"""
        tweet_id = context.post_id
        actions_taken: List[str] = []
        reply_content = None

        # 아무 액션도 없으면 skip
        if not judgment.like and not judgment.repost and not judgment.reply:
            return ScenarioResult(success=True, action='skip')

        # Like 실행
        if judgment.like:
            logger.info(f"[Scenario:FamiliarPerson] Executing: like")
            if twitter_api.like_tweet(tweet_id):
                actions_taken.append('like')

        # Repost 실행
        if judgment.repost:
            logger.info(f"[Scenario:FamiliarPerson] Executing: repost")
            if twitter_api.repost_tweet(tweet_id):
                actions_taken.append('repost')

        # Reply 실행
        if judgment.reply:
            logger.info(f"[Scenario:FamiliarPerson] Executing: reply (type={judgment.reply_type or 'normal'})")
            recent_replies = self.get_recent_replies(limit=5)
            post_data = context.extra.get('post', {}) if context.extra else {}

            # context 조합 (existing_replies + author_profile)
            reply_context = {}
            if post_data.get('replies'):
                reply_context['existing_replies'] = post_data['replies']
            if post_data.get('author_profile'):
                reply_context['author_profile'] = post_data['author_profile']

            reply_content = self.reply_gen.generate(
                post_text=context.post_text or "",
                person=context.person,
                reply_type=judgment.reply_type or 'normal',
                recent_replies=recent_replies,
                context=reply_context if reply_context else None
            )

            if reply_content:
                result = twitter_api.reply_to_tweet(tweet_id, reply_content)
                if result is not None:
                    actions_taken.append('reply')
            else:
                logger.warning("[Scenario:FamiliarPerson] Reply generation failed")

        # 결과 반환
        primary_action = 'reply' if 'reply' in actions_taken else ('repost' if 'repost' in actions_taken else ('like' if 'like' in actions_taken else 'skip'))

        return ScenarioResult(
            success=len(actions_taken) > 0,
            action=primary_action,
            content=reply_content,
            details={'actions': actions_taken, 'reason': judgment.reason}
        )

    def _update_memory(self, context: ScenarioContext, result: ScenarioResult):
        """메모리 업데이트"""
        actions = result.details.get('actions', [])
        if context.person and actions:
            for action in actions:
                if action in ('like', 'reply', 'repost'):
                    self.update_person_after_interaction(
                        context.person,
                        interaction_type=action
                    )

            if context.conversation and 'reply' in actions:
                self.update_conversation_after_turn(
                    context.conversation,
                    summary=f"Replied to their post"
                )
