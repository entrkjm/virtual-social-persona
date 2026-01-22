"""
Notification Journey
알림 확인 → 시나리오 분기 → 실행

Entry point for notification-centric social mode
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .base import BaseJourney, JourneyResult
from agent.memory.database import MemoryDatabase
from agent.memory.session import agent_memory
from agent.platforms.twitter.api.social import get_all_notifications, NotificationData

logger = logging.getLogger("agent")

from ..scenarios.notification.received_comment import ReceivedCommentScenario
from ..scenarios.notification.mentioned import MentionedScenario
from ..scenarios.notification.quoted import QuotedScenario
from ..scenarios.notification.new_follower import NewFollowerScenario
from ..scenarios.notification.reposted import RepostedScenario


@dataclass
class ProcessedNotification:
    """처리된 알림 + 메타데이터"""
    raw: NotificationData
    scenario_type: str
    priority: int


class NotificationJourney(BaseJourney):
    """
    알림 기반 소셜 활동 Journey

    Flow:
    1. 알림 fetch (get_all_notifications)
    2. 시나리오별 분류 + 우선순위 정렬
    3. 상위 N개 처리 (기본 1개)
    """

    SCENARIO_PRIORITY = {
        'reply': 1,      # 내 글에 답글 → 가장 중요
        'mention': 2,    # 멘션
        'quote': 3,      # 인용
        'follow': 4,     # 팔로우
        'like': 10,      # 좋아요 → 낮은 우선순위
        'retweet': 10,
        'unknown': 99
    }

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter', persona_config: Optional[Dict] = None):
        super().__init__(memory_db, platform)
        self.persona_config = persona_config
        self._init_scenarios()

    def _init_scenarios(self):
        """시나리오 인스턴스 초기화"""
        self.scenarios = {
            'reply': ReceivedCommentScenario(self.memory_db, self.platform, self.persona_config),
            'mention': MentionedScenario(self.memory_db, self.platform, self.persona_config),
            'quote': QuotedScenario(self.memory_db, self.platform, self.persona_config),
            'follow': NewFollowerScenario(self.memory_db, self.platform, self.persona_config),
            'retweet': RepostedScenario(self.memory_db, self.platform, self.persona_config)
        }

    def run(self, count: int = 20, process_limit: int = 1) -> Optional[JourneyResult]:
        """
        알림 확인 및 처리

        Args:
            count: 가져올 알림 수
            process_limit: 처리할 알림 수 (기본 1개)
        """
        notifications = get_all_notifications(count=count)
        if not notifications:
            logger.info("[Notification] No notifications fetched")
            return None

        logger.info(f"[Notification] Fetched {len(notifications)} notifications")

        classified = self._classify_and_prioritize(notifications)
        if not classified:
            logger.info("[Notification] No actionable notifications (all filtered)")
            return None

        logger.info(f"[Notification] {len(classified)} actionable: {[n.scenario_type for n in classified[:10]]}")

        for notif in classified[:process_limit]:
            logger.info(f"[Notification] Processing: {notif.scenario_type} from @{notif.raw.get('from_user')}")
            result = self._process_notification(notif)
            if result and result.success:
                return result

        return None

    def _classify_and_prioritize(
        self, notifications: List[NotificationData]
    ) -> List[ProcessedNotification]:
        """알림 분류 + 우선순위 정렬 + 이미 처리된 알림 필터링"""
        processed = []
        type_counts = {}
        skipped_count = 0

        for notif in notifications:
            notif_id = notif.get('id', '')
            notif_type = notif.get('type', 'unknown')
            from_user_id = notif.get('from_user_id', '')

            type_counts[notif_type] = type_counts.get(notif_type, 0) + 1

            # 이미 처리된 알림 스킵
            if agent_memory.is_notification_processed(notif_id):
                skipped_count += 1
                continue

            # follow의 경우 이미 팔로우백한 유저 스킵
            if notif_type == 'follow' and agent_memory.is_user_already_followed_back(from_user_id):
                skipped_count += 1
                continue

            priority = self.SCENARIO_PRIORITY.get(notif_type, 99)

            # 처리 가능한 시나리오만 포함
            if notif_type in self.scenarios:
                processed.append(ProcessedNotification(
                    raw=notif,
                    scenario_type=notif_type,
                    priority=priority
                ))

        logger.info(f"[Notification] Type breakdown: {type_counts}, skipped: {skipped_count}")
        processed.sort(key=lambda x: x.priority)
        return processed

    def _process_notification(self, notif: ProcessedNotification) -> Optional[JourneyResult]:
        """단일 알림 처리"""
        scenario = self.scenarios.get(notif.scenario_type)
        if not scenario:
            return None

        notif_id = notif.raw.get('id', '')
        notif_type = notif.scenario_type
        from_user_id = notif.raw.get('from_user_id', '')

        try:
            result = scenario.execute(notif.raw)

            # 처리 완료 기록
            if result:
                action = result.action or 'skipped'
                agent_memory.mark_notification_processed(notif_id, notif_type, from_user_id, action)

            return JourneyResult(
                success=result.success if result else False,
                scenario_executed=notif.scenario_type,
                action_taken=result.action if result else None,
                target_user=notif.raw.get('from_user'),
                details=result.details if result else None
            )
        except Exception as e:
            error_str = str(e).lower()
            # 226/401/403/authorization 에러는 상위로 전파 (쿨다운 처리 필요)
            if any(code in error_str for code in ['226', '401', '403', 'authorization', 'automated']):
                raise
            print(f"[NotificationJourney] Scenario {notif.scenario_type} failed: {e}")
            return None
