"""
Posting Trigger Engine
글쓰기 발현 트리거 시스템
Determines when and why to write posts
"""
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from config.settings import settings
from agent.memory.database import MemoryDatabase, Episode, Inspiration
from agent.memory.inspiration_pool import InspirationPool, InspirationTrigger


@dataclass
class PostingDecision:
    """글쓰기 결정"""
    type: str  # 'flash', 'flash_reinforced', 'ready', 'mood_burst', 'random_recall'
    source: Any  # Episode or Inspiration
    urgency: str  # 'immediate', 'soon', 'whenever'
    reason: str
    inspiration_id: Optional[str] = None


@dataclass
class TriggerConfig:
    """트리거 설정"""
    impact_threshold: float
    probability: float


class PostingTriggerEngine:
    """글쓰기 트리거 엔진"""

    def __init__(
        self,
        db: Optional[MemoryDatabase] = None,
        inspiration_pool: Optional[InspirationPool] = None
    ):
        from agent.memory.database import memory_db
        from agent.memory.inspiration_pool import inspiration_pool as pool

        self.db = db or memory_db
        self.inspiration_pool = inspiration_pool or pool

        # BehaviorEngine은 선택적 의존성
        self._behavior_engine = None

        # 빈도 제한 설정
        self.max_posts_per_day = 5
        self.min_interval_minutes = settings.POST_MIN_INTERVAL

        # 트리거 설정
        self.triggers = {
            'flash': TriggerConfig(impact_threshold=0.9, probability=settings.PROB_FLASH),
            'flash_reinforced': TriggerConfig(impact_threshold=0.8, probability=settings.PROB_FLASH_REINFORCED),
            'mood_burst': TriggerConfig(impact_threshold=0.8, probability=settings.PROB_MOOD_BURST),
            'random_recall': TriggerConfig(impact_threshold=0.0, probability=settings.PROB_RANDOM_RECALL)
        }

        # 마지막 포스팅 시간 추적
        self.last_post_time: Optional[datetime] = None
        self.today_post_count = 0
        self.last_reset_date = datetime.now().date()

    @property
    def behavior_engine(self):
        """BehaviorEngine 지연 로딩"""
        if self._behavior_engine is None:
            try:
                from agent.behavior_engine import behavior_engine
                self._behavior_engine = behavior_engine
            except ImportError:
                pass
        return self._behavior_engine

    def _reset_daily_counters_if_needed(self):
        """일일 카운터 리셋"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.today_post_count = 0
            self.last_reset_date = today

    def check_trigger(self, context: Dict[str, Any]) -> Optional[PostingDecision]:
        """매 step마다 호출하여 글쓰기 트리거 확인

        Args:
            context: {
                'current_episode': Episode,  # 방금 본 에피소드 (optional)
                'reinforcement_trigger': InspirationTrigger,  # 강화 트리거 (optional)
            }

        Returns:
            PostingDecision if triggered, None otherwise
        """
        self._reset_daily_counters_if_needed()

        # 빈도 제한 체크
        if not self._can_post_now():
            return None

        # 1. Flash - 방금 본 게 너무 인상적
        decision = self._check_flash_trigger(context)
        if decision:
            return decision

        # 2. Flash Reinforced - 관심사에 또 자극
        decision = self._check_flash_reinforced_trigger(context)
        if decision:
            return decision

        # 3. Ready - 숙성된 영감 발현
        decision = self._check_ready_trigger(context)
        if decision:
            return decision

        # 4. Mood Burst - 기분 좋아서
        decision = self._check_mood_burst_trigger()
        if decision:
            return decision

        # 5. Random Recall - 갑자기 생각남
        decision = self._check_random_recall_trigger()
        if decision:
            return decision

        return None

    def _can_post_now(self) -> bool:
        """빈도 제한 체크"""
        # 일일 최대 개수 체크
        if self.today_post_count >= self.max_posts_per_day:
            return False

        # 최소 간격 체크
        if self.last_post_time:
            minutes_since = (datetime.now() - self.last_post_time).total_seconds() / 60
            if minutes_since < self.min_interval_minutes:
                return False

        return True

    def _check_flash_trigger(self, context: Dict[str, Any]) -> Optional[PostingDecision]:
        """Flash 트리거: 방금 본 게 임팩트 있음"""
        current_episode = context.get('current_episode')
        if not current_episode:
            return None

        config = self.triggers['flash']

        if current_episode.emotional_impact >= config.impact_threshold:
            if random.random() < config.probability:
                return PostingDecision(
                    type='flash',
                    source=current_episode,
                    urgency='immediate',
                    reason='필 꽂힘'
                )

        return None

    def _check_flash_reinforced_trigger(
        self, context: Dict[str, Any]
    ) -> Optional[PostingDecision]:
        """Flash Reinforced 트리거: 관심사에 또 자극받음"""
        reinforcement_trigger = context.get('reinforcement_trigger')
        if not reinforcement_trigger:
            return None

        if reinforcement_trigger.type != 'flash_reinforced':
            return None

        config = self.triggers['flash_reinforced']

        if random.random() < config.probability:
            return PostingDecision(
                type='flash_reinforced',
                source=reinforcement_trigger.inspiration,
                urgency='immediate',
                reason=reinforcement_trigger.reason,
                inspiration_id=reinforcement_trigger.inspiration.id
                if reinforcement_trigger.inspiration else None
            )

        return None

    def _check_ready_trigger(self, context: Dict[str, Any]) -> Optional[PostingDecision]:
        """Ready 트리거: 숙성된 영감이 비슷한 주제를 만남"""
        current_episode = context.get('current_episode')
        ready_inspirations = self._get_ready_inspirations()

        if not ready_inspirations:
            return None

        # 현재 에피소드가 있으면 주제 매칭 확인
        if current_episode:
            for insp in ready_inspirations:
                if self._topic_matches(insp, current_episode):
                    return PostingDecision(
                        type='ready',
                        source=insp,
                        urgency='soon',
                        reason=f"'{insp.topic}' 관련 또 봄",
                        inspiration_id=insp.id
                    )

        return None

    def _check_mood_burst_trigger(self) -> Optional[PostingDecision]:
        """Mood Burst 트리거: 기분 좋아서 글 쓰고 싶음"""
        if not self.behavior_engine:
            return None

        config = self.triggers['mood_burst']

        if self.behavior_engine.current_mood < config.impact_threshold:
            return None

        ready_inspirations = self._get_ready_inspirations()
        if not ready_inspirations:
            return None

        if random.random() < config.probability:
            chosen = random.choice(ready_inspirations)
            return PostingDecision(
                type='mood_burst',
                source=chosen,
                urgency='soon',
                reason='기분 좋아서 글 쓰고 싶음',
                inspiration_id=chosen.id
            )

        return None

    def _check_random_recall_trigger(self) -> Optional[PostingDecision]:
        """Random Recall 트리거: 갑자기 생각남"""
        config = self.triggers['random_recall']

        ready_inspirations = self._get_ready_inspirations()
        if not ready_inspirations:
            return None

        if random.random() < config.probability:
            chosen = random.choice(ready_inspirations)
            return PostingDecision(
                type='random_recall',
                source=chosen,
                urgency='whenever',
                reason='갑자기 생각남',
                inspiration_id=chosen.id
            )

        return None

    def _get_ready_inspirations(self) -> List[Inspiration]:
        """발현 준비된 영감들"""
        return self.db.get_ready_inspirations(
            min_strength=0.4,
            tiers=['long_term', 'core'],
            maturation_hours=24,
            cooldown_days=7,
            limit=10
        )

    def _topic_matches(self, inspiration: Inspiration, episode: Episode) -> bool:
        """영감과 에피소드의 주제가 매칭되는지 확인"""
        if not inspiration.topic or not episode.topics:
            return False

        insp_topic_lower = inspiration.topic.lower()
        episode_topics_lower = [t.lower() for t in episode.topics]

        # 직접 매칭
        if insp_topic_lower in episode_topics_lower:
            return True

        # 부분 매칭 (영감 주제가 에피소드 주제에 포함되거나 그 반대)
        for ep_topic in episode_topics_lower:
            if insp_topic_lower in ep_topic or ep_topic in insp_topic_lower:
                return True

        return False

    def record_post(self, decision: PostingDecision):
        """포스팅 기록"""
        self.last_post_time = datetime.now()
        self.today_post_count += 1

        # 영감을 사용한 경우 기록
        if decision.inspiration_id:
            insp = self.db.get_inspiration(decision.inspiration_id)
            if insp:
                self.inspiration_pool.on_posted(insp)

        print(f"[POSTING TRIGGER] Recorded: {decision.type} - {decision.reason}")

    def get_trigger_context_for_llm(self, decision: PostingDecision) -> str:
        """LLM에 주입할 트리거 컨텍스트 생성"""
        context = f"### 🔥 POSTING TRIGGER: {decision.type.upper()}\n"
        context += f"**이유**: {decision.reason}\n"
        context += f"**긴급도**: {decision.urgency}\n"

        if isinstance(decision.source, Episode):
            context += f"**원본**: {decision.source.content[:200]}...\n"
        elif isinstance(decision.source, Inspiration):
            context += f"**주제**: {decision.source.topic}\n"
            if decision.source.my_angle:
                context += f"**내 관점**: {decision.source.my_angle}\n"
            if decision.source.potential_post:
                context += f"**초안**: {decision.source.potential_post}\n"

        return context

    def get_stats(self) -> Dict[str, Any]:
        """통계"""
        self._reset_daily_counters_if_needed()

        return {
            'today_post_count': self.today_post_count,
            'max_posts_per_day': self.max_posts_per_day,
            'can_post_now': self._can_post_now(),
            'last_post_time': self.last_post_time.isoformat() if self.last_post_time else None,
            'ready_inspirations_count': len(self._get_ready_inspirations())
        }


# Global instance
posting_trigger = PostingTriggerEngine()
