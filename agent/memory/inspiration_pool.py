"""
Inspiration Pool
영감 저장소 + 강화 엔진
Inspiration storage and reinforcement engine
"""
import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from agent.memory.database import MemoryDatabase, Inspiration, Episode, generate_id


def normalize_topic(topic: str) -> str:
    """토픽 정규화: 공백 제거, 소문자화"""
    if not topic:
        return "general"
    # 공백 제거 + 소문자
    normalized = re.sub(r'\s+', '', topic.strip().lower())
    return normalized if normalized else "general"
from agent.memory.tier_manager import TierManager

try:
    from agent.memory.vector_store import VectorStore
except ImportError:
    VectorStore = None


@dataclass
class InspirationTrigger:
    """영감 발현 트리거"""
    type: str  # 'flash', 'flash_reinforced', 'ready', 'mood_burst', 'random_recall'
    inspiration: Optional[Inspiration]
    episode: Optional[Episode]
    reason: str


class InspirationPool:
    """영감 저장소 + 강화 엔진"""

    def __init__(
        self,
        db: Optional[MemoryDatabase] = None,
        vector_store: Optional[VectorStore] = None,
        tier_manager: Optional[TierManager] = None
    ):
        from agent.memory.database import memory_db
        from agent.memory.tier_manager import tier_manager as tm

        try:
            from agent.memory.vector_store import vector_store as vs
        except ImportError:
            vs = None

        self.db = db or memory_db
        self.vector_store = vector_store or vs
        self.tier_manager = tier_manager or tm

        # 강화 설정
        self.REINFORCEMENT_CONFIG = {
            'similar_content_seen': {'strength': 0.1, 'count': 1},
            'same_topic_searched': {'strength': 0.05, 'count': 1},
            'posted_about': {'strength': 0.3, 'count': 3},
            'accessed': {'strength': 0.05, 'count': 0},
        }
        self.SIMILARITY_THRESHOLD = 0.3  # Chroma 거리 기준 (낮을수록 유사)

    # ==================== 영감 생성 ====================

    def create_inspiration_from_episode(
        self,
        episode: Episode,
        my_angle: str,
        urgency: str = 'brewing'  # 'flash' or 'brewing'
    ) -> Inspiration:
        """에피소드로부터 영감 생성

        Args:
            episode: 원본 에피소드
            my_angle: 내 관점/해석
            urgency: 'flash' (즉각) or 'brewing' (숙성)

        Returns:
            생성된 Inspiration (또는 강화된 기존 Inspiration)
        """
        # 토픽 정규화 (공백 제거)
        raw_topic = episode.topics[0] if episode.topics else "general"
        topic = normalize_topic(raw_topic)

        # 기존 동일 토픽 영감 있으면 강화
        existing = self.db.get_inspiration_by_topic(topic)
        if existing:
            self._reinforce(existing, 'similar_content')
            print(f"[INSPIRATION] Reinforced existing: {topic} (strength={existing.strength:.2f})")
            return existing

        insp_id = generate_id()
        now = datetime.now()

        # 초기 강도 결정
        if urgency == 'flash':
            initial_strength = 0.8  # Flash는 높은 강도로 시작
            initial_tier = 'short_term'  # 바로 short_term으로
        else:
            initial_strength = 0.5
            initial_tier = 'ephemeral'

        insp = Inspiration(
            id=insp_id,
            episode_id=episode.id,
            trigger_content=episode.content,
            topic=topic,
            my_angle=my_angle,
            potential_post=None,
            tier=initial_tier,
            strength=initial_strength,
            emotional_impact=episode.emotional_impact,
            reinforcement_count=0,
            created_at=now,
            last_reinforced_at=now,
            last_accessed_at=None,
            used_count=0,
            last_used_at=None
        )

        # DB 저장
        self.db.add_inspiration(insp)

        # Vector Store 저장 (trigger_content + my_angle 조합)
        if self.vector_store:
            search_text = f"{episode.content} | {my_angle}"
            self.vector_store.add_inspiration(
                id=insp_id,
                content=search_text,
                metadata={
                    'tier': insp.tier,
                    'strength': insp.strength,
                    'topic': insp.topic,
                    'emotional_impact': insp.emotional_impact
                }
            )

        print(f"[INSPIRATION] Created: {insp.topic} ({urgency}, tier={initial_tier})")
        return insp

    # ==================== 강화 (Reinforcement) ====================

    def on_content_seen(
        self,
        content: str,
        emotional_impact: float = 0.5
    ) -> Optional[InspirationTrigger]:
        """새 콘텐츠를 봤을 때 - 유사한 영감 강화

        Args:
            content: 새로 본 콘텐츠
            emotional_impact: 감정적 임팩트 (0.0 ~ 1.0)

        Returns:
            Flash 트리거 발생 시 InspirationTrigger
        """
        # vector_store 없으면 skip
        if not self.vector_store:
            return None

        # 유사한 영감 검색
        similar = self.vector_store.find_reinforcement_candidates(
            content=content,
            similarity_threshold=self.SIMILARITY_THRESHOLD,
            n_results=5
        )

        if not similar:
            return None

        flash_trigger = None

        for match in similar:
            insp = self.db.get_inspiration(match['id'])
            if not insp:
                continue

            # 강화
            self._reinforce(insp, 'similar_content_seen')

            # Flash 판단: 비슷한 거 또 보는데 임팩트도 높고 강도도 높다?
            if emotional_impact >= 0.8 and insp.strength >= 0.5:
                flash_trigger = InspirationTrigger(
                    type='flash_reinforced',
                    inspiration=insp,
                    episode=None,
                    reason=f"관심사 '{insp.topic}'에 또 자극받음"
                )

        return flash_trigger

    def on_topic_searched(self, topic: str) -> List[Inspiration]:
        """특정 주제를 검색했을 때 - 관련 영감 강화

        Returns:
            강화된 영감 목록
        """
        if not self.vector_store:
            return []

        similar = self.vector_store.search_similar_inspirations(
            query=topic,
            n_results=5
        )

        reinforced = []
        for match in similar:
            insp = self.db.get_inspiration(match['id'])
            if insp:
                self._reinforce(insp, 'same_topic_searched')
                reinforced.append(insp)

        return reinforced

    def on_posted(self, insp: Inspiration):
        """영감을 사용해서 글을 썼을 때"""
        self._reinforce(insp, 'posted_about')

        insp.used_count += 1
        insp.last_used_at = datetime.now()

        # 최소 long_term 보장
        if insp.tier in ['ephemeral', 'short_term']:
            insp.tier = 'long_term'

        self.db.update_inspiration(insp)
        self._sync_vector_metadata(insp)

        print(f"[INSPIRATION] Used for posting: {insp.topic}")

    def _reinforce(self, insp: Inspiration, reason: str):
        """영감 강화"""
        config = self.REINFORCEMENT_CONFIG.get(reason, {'strength': 0.05, 'count': 1})

        insp.strength = min(1.0, insp.strength + config['strength'])
        insp.reinforcement_count += config['count']
        insp.last_reinforced_at = datetime.now()

        # 승격 체크
        if self.tier_manager.promote(insp):
            print(f"[INSPIRATION] Promoted to {insp.tier}: {insp.topic}")

            # Core로 승격 시 페르소나 통합
            if insp.tier == 'core':
                core_memory = self.tier_manager.create_core_memory_from_inspiration(insp)
                self.db.add_core_memory(core_memory)
                print(f"[CORE MEMORY] Created: {core_memory.content}")

        self.db.update_inspiration(insp)
        self._sync_vector_metadata(insp)

    def _sync_vector_metadata(self, insp: Inspiration):
        """Vector Store 메타데이터 동기화"""
        if not self.vector_store:
            return

        self.vector_store.update_inspiration_metadata(
            id=insp.id,
            metadata={
                'tier': insp.tier,
                'strength': insp.strength,
                'topic': insp.topic,
                'emotional_impact': insp.emotional_impact,
                'reinforcement_count': insp.reinforcement_count
            }
        )

    # ==================== 영감 조회 ====================

    def get_ready_inspirations(self) -> List[Inspiration]:
        """발현 준비된 영감들 (long_term/core, 숙성 완료)"""
        return self.db.get_ready_inspirations()

    def find_similar(self, content: str, n_results: int = 5) -> List[Dict]:
        """유사한 영감 검색"""
        if not self.vector_store:
            return []

        return self.vector_store.search_similar_inspirations(
            query=content,
            n_results=n_results
        )

    def get_by_tier(self, tier: str) -> List[Inspiration]:
        """티어별 영감 조회"""
        return self.db.get_inspirations_by_tier(tier)

    def get_stats(self) -> Dict[str, Any]:
        """통계"""
        tier_counts = self.db.count_inspirations_by_tier()

        vector_count = 0
        if self.vector_store:
            vector_stats = self.vector_store.get_stats()
            vector_count = vector_stats['inspirations_count']

        return {
            'by_tier': tier_counts,
            'total': sum(tier_counts.values()),
            'vector_count': vector_count
        }

    # ==================== Flash 판단 ====================

    def evaluate_flash_potential(
        self,
        episode: Episode,
        threshold: float = 0.9
    ) -> Optional[InspirationTrigger]:
        """에피소드의 Flash 잠재력 평가

        Args:
            episode: 방금 본 에피소드
            threshold: Flash 임계값 (emotional_impact)

        Returns:
            Flash 트리거 발생 시 InspirationTrigger
        """
        if episode.emotional_impact >= threshold:
            return InspirationTrigger(
                type='flash',
                inspiration=None,
                episode=episode,
                reason='필 꽂힘'
            )
        return None


# Global instance
inspiration_pool = InspirationPool()
