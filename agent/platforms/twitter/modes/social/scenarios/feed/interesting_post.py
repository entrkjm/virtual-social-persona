"""
Interesting Post Scenario
관심있는 주제의 글을 발견했을 때

HYBRID v1에서 FeedJourney가 rule-based로 선택한 후 실행됨
"""
import logging
from typing import Optional, Dict, Any, List

from ..base import BaseScenario, ScenarioResult, ScenarioContext
from agent.memory.database import MemoryDatabase
from agent.platforms.twitter.api import social as twitter_api
from ...judgment import EngagementJudge, ReplyGenerator
from ...judgment.engagement_judge import JudgmentResult

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

        judgment = self._judge(context)
        logger.info(f"[Scenario:InterestingPost] Judge: like={judgment.like}, repost={judgment.repost}, reply={judgment.reply}")

        result = self._execute_actions(context, judgment)
        logger.info(f"[Scenario:InterestingPost] Result: success={result.success if result else False}, actions={result.details.get('actions') if result else 'none'}")

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
            scenario_type='interesting_post',
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
            logger.info(f"[Scenario:InterestingPost] Executing: like")
            if twitter_api.like_tweet(tweet_id):
                actions_taken.append('like')

        # Repost 실행
        if judgment.repost:
            logger.info(f"[Scenario:InterestingPost] Executing: repost")
            if twitter_api.repost_tweet(tweet_id):
                actions_taken.append('repost')

        # Reply 실행
        if judgment.reply:
            logger.info(f"[Scenario:InterestingPost] Executing: reply (type={judgment.reply_type or 'normal'})")
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
                logger.warning("[Scenario:InterestingPost] Reply generation failed")

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
