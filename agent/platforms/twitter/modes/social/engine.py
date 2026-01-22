"""
Social Mode Engine
통합 진입점 - NotificationJourney와 FeedJourney 오케스트레이션

기존 SocialAgent와 통합하여 사용
"""
import random
from typing import Optional, Dict, Any, List

from agent.core.logger import logger
from agent.memory.database import MemoryDatabase
from agent.memory.factory import MemoryFactory

from .journeys.notification import NotificationJourney
from .journeys.feed import FeedJourney
from .journeys.base import JourneyResult


class SocialEngine:
    """
    Social Mode 통합 엔진

    Usage:
        engine = SocialEngine(persona_id='chef_choi', persona_config=config)
        result = engine.run_notification_journey()  # 알림 우선
        result = engine.run_feed_journey(posts)      # 피드 탐색
    """

    def __init__(
        self,
        persona_id: str,
        persona_config: Optional[Dict] = None,
        platform: str = 'twitter'
    ):
        self.persona_id = persona_id
        self.persona_config = persona_config or {}
        self.platform = platform
        self.activity_config = self.persona_config.get('activity', {})

        # 메모리 DB
        self.memory_db = MemoryFactory.get_memory_db(persona_id)

        # 관심 키워드 추출
        self.core_interests = self._extract_core_interests()

        # Journey 인스턴스
        self.notification_journey = NotificationJourney(
            self.memory_db, platform, persona_config
        )
        feed_selection = self.activity_config.get('social', {}).get('feed_selection', {})
        self.feed_journey = FeedJourney(
            self.memory_db,
            platform,
            self.core_interests,
            persona_config,
            feed_selection=feed_selection
        )

    def _extract_core_interests(self) -> List[str]:
        """페르소나 설정에서 관심 키워드 추출"""
        identity = self.persona_config.get('identity', {})
        keywords = identity.get('core_keywords', [])

        # search_keywords도 포함
        if identity.get('search_keywords'):
            keywords.extend(identity['search_keywords'])

        return list(set(keywords))

    def run_notification_journey(
        self,
        count: int = 20,
        process_limit: int = 1
    ) -> Optional[JourneyResult]:
        """
        알림 Journey 실행

        Returns:
            JourneyResult or None
        """
        try:
            result = self.notification_journey.run(
                count=count,
                process_limit=process_limit
            )
            if result:
                logger.info(
                    f"[Social] Notification: {result.scenario_executed} -> {result.action_taken}"
                )
            return result
        except Exception as e:
            error_str = str(e).lower()
            # 226/401/403/authorization 에러는 상위로 전파
            if any(code in error_str for code in ['226', '401', '403', 'authorization', 'automated']):
                raise
            logger.error(f"[Social] Notification journey failed: {e}")
            return None

    def run_feed_journey(
        self,
        posts: List[Dict[str, Any]],
        process_limit: int = 1
    ) -> Optional[JourneyResult]:
        """
        피드 Journey 실행

        Args:
            posts: 검색된 포스트 목록
        """
        try:
            result = self.feed_journey.run(
                posts=posts,
                process_limit=process_limit
            )
            if result:
                logger.info(
                    f"[Social] Feed: {result.scenario_executed} -> {result.action_taken}"
                )
            return result
        except Exception as e:
            error_str = str(e).lower()
            # 226/401/403/authorization 에러는 상위로 전파
            if any(code in error_str for code in ['226', '401', '403', 'authorization', 'automated']):
                raise
            logger.error(f"[Social] Feed journey failed: {e}")
            return None

    def step(
        self,
        posts: Optional[List[Dict[str, Any]]] = None,
        notification_weight: float = 0.6
    ) -> Optional[JourneyResult]:
        """
        단일 step 실행 (알림 vs 피드 가중치 기반)

        Args:
            posts: 피드 탐색용 포스트 (없으면 알림만)
            notification_weight: 알림 확인 확률 (기본 60%)
        """
        activity_weight = self._get_notification_weight()
        final_weight = activity_weight if activity_weight is not None else notification_weight
        roll = random.random()

        # 알림 우선 (notification_weight 확률)
        if roll < final_weight:
            logger.info(f"[Social] Journey: notification (roll={roll:.2f} < {final_weight:.2f})")
            result = self.run_notification_journey()
            if result and result.success:
                return result

        # 피드 탐색
        if posts:
            logger.info(f"[Social] Journey: feed (roll={roll:.2f} >= {final_weight:.2f})")
            result = self.run_feed_journey(posts)
            if result and result.success:
                return result

        # 둘 다 실패 시 알림 재시도 (아직 안 했다면)
        if roll >= final_weight:
            logger.info(f"[Social] Journey: notification (fallback)")
            return self.run_notification_journey()

        return None

    def _get_notification_weight(self) -> Optional[float]:
        """activity.yaml 기반 알림 가중치 계산"""
        journey_weights = self.activity_config.get('social', {}).get('journey_weights', {})
        if not journey_weights:
            return None
        notification = float(journey_weights.get('notification', 0.0))
        feed = float(journey_weights.get('feed', 0.0))
        total = notification + feed
        if total <= 0:
            return None
        return notification / total
