"""
Profile Visit Journey
팔로잉 중인 사람 프로필 방문 → 최근 글 확인 → 상호작용

상호작용 시작점 문제 해결:
- 두 페르소나가 서로 팔로우만 하고 있으면 검색/알림으로는 접점이 안 생김
- 직접 프로필 방문해서 글에 반응함으로써 대화 시작
"""
import logging
import random
from typing import Optional, List, Dict, Any

from .base import BaseJourney, JourneyResult
from agent.memory.database import MemoryDatabase, PersonMemory
from ..scenarios.feed.familiar_person import FamiliarPersonScenario
from ..scenarios.feed.interesting_post import InterestingPostScenario

logger = logging.getLogger("agent")


class ProfileVisitJourney(BaseJourney):
    """
    프로필 방문 Journey

    Flow:
    1. 팔로잉 목록에서 방문 대상 선택
       - familiar_first: affinity 높은 사람 우선
       - random_prob: 일정 확률로 랜덤 선택
    2. 대상 프로필의 최근 글 가져오기
    3. FamiliarPerson 시나리오로 상호작용 판단
    """

    def __init__(
        self,
        memory_db: MemoryDatabase,
        platform: str = 'twitter',
        persona_config: Optional[Dict] = None,
        visit_config: Optional[Dict] = None
    ):
        super().__init__(memory_db, platform)
        self.persona_config = persona_config or {}
        self.visit_config = visit_config or {}

        target_cfg = self.visit_config.get('target', {})
        self.familiar_first = target_cfg.get('familiar_first', True)
        self.random_prob = target_cfg.get('random_prob', 0.2)
        self.posts_to_check = self.visit_config.get('posts_to_check', [1, 3])

        self._init_scenarios()

    def _init_scenarios(self):
        self.scenarios = {
            'familiar_person': FamiliarPersonScenario(
                self.memory_db, self.platform, self.persona_config
            ),
            'interesting_post': InterestingPostScenario(
                self.memory_db, self.platform, self.persona_config
            )
        }

    def run(
        self,
        following_list: List[Dict[str, Any]],
        get_user_tweets_fn,
        process_limit: int = 1
    ) -> Optional[JourneyResult]:
        """
        프로필 방문 실행

        Args:
            following_list: 팔로잉 목록 [{'user_id': str, 'screen_name': str}, ...]
            get_user_tweets_fn: 유저 트윗 가져오는 함수 (user_id, count) -> List[dict]
            process_limit: 처리할 프로필 수
        """
        if not following_list:
            logger.info("[ProfileVisit] No following list provided")
            return None

        target = self._select_target(following_list)
        if not target:
            logger.info("[ProfileVisit] No target selected")
            return None

        user_id = target.get('user_id', '')
        screen_name = target.get('screen_name', '')
        logger.info(f"[ProfileVisit] Visiting @{screen_name}")

        posts_count = random.randint(self.posts_to_check[0], self.posts_to_check[1])
        posts = get_user_tweets_fn(user_id=user_id, count=posts_count)

        if not posts:
            logger.info(f"[ProfileVisit] No posts from @{screen_name}")
            return None

        logger.info(f"[ProfileVisit] Found {len(posts)} posts from @{screen_name}")

        person = self.get_person(user_id, screen_name)
        is_familiar = person.tier in ('familiar', 'friend')

        for post in posts:
            scenario_type = 'familiar_person' if is_familiar else 'interesting_post'
            result = self._run_scenario(post, scenario_type)
            if result and result.success and result.action_taken:
                return result

        return JourneyResult(
            success=True,
            scenario_executed='profile_visit',
            action_taken=None,
            target_user=screen_name,
            details={'posts_checked': len(posts)}
        )

    def _select_target(self, following_list: List[Dict]) -> Optional[Dict]:
        """방문 대상 선택"""
        if random.random() < self.random_prob:
            return random.choice(following_list)

        if self.familiar_first:
            familiar_targets = []
            for f in following_list:
                user_id = f.get('user_id', '')
                screen_name = f.get('screen_name', '')
                person = self.memory_db.get_person(user_id, self.platform)
                if person and person.tier in ('familiar', 'friend'):
                    familiar_targets.append((f, person.affinity))

            if familiar_targets:
                familiar_targets.sort(key=lambda x: x[1], reverse=True)
                return familiar_targets[0][0]

        return random.choice(following_list)

    def _run_scenario(self, post: Dict, scenario_type: str) -> Optional[JourneyResult]:
        scenario = self.scenarios.get(scenario_type)
        if not scenario:
            return None

        try:
            result = scenario.execute(post)
            if result:
                return JourneyResult(
                    success=result.success,
                    scenario_executed=f"profile_visit:{scenario_type}",
                    action_taken=result.action if result else None,
                    target_user=post.get('user'),
                    details=result.details if result else None
                )
        except Exception as e:
            error_str = str(e).lower()
            if any(code in error_str for code in ['226', '401', '403', 'authorization']):
                raise
            logger.error(f"[ProfileVisit] Scenario failed: {e}")

        return None
