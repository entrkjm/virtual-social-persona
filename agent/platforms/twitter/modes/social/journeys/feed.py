"""
Feed Journey
피드 탐색 → 분류 → 1개 선택 → 시나리오 실행

HYBRID v1: Rule-based classification → priority selection → LLM judgment on 1 post
TODO(v2): Per-post individual LLM judgment
"""
import random
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass

from .base import BaseJourney, JourneyResult
from agent.memory.database import MemoryDatabase, PersonMemory

from ..scenarios.feed.familiar_person import FamiliarPersonScenario
from ..scenarios.feed.interesting_post import InterestingPostScenario


@dataclass
class ClassifiedPosts:
    """분류된 포스트들 (HYBRID v1: Rule-based, no LLM)"""
    familiar: List[Tuple[Dict, PersonMemory]]  # (post, person)
    interesting: List[Dict]
    others: List[Dict]


class FeedJourney(BaseJourney):
    """
    피드 탐색 Journey

    HYBRID v1 Flow:
    1. 피드에서 N개 포스트 가져오기
    2. Rule-based 분류 (LLM 없음)
       - familiar: 아는 사람 (tier=familiar/friend)
       - interesting: 관심 키워드 매칭
       - others: 나머지
    3. 우선순위 기반 1개 선택
       - familiar > interesting > random(10%)
    4. 선택된 1개에 대해 시나리오 실행 (LLM 판단)

    비용: 8개 가져와도 LLM은 1-2회만 호출
    """

    RANDOM_DISCOVERY_PROB = 0.10  # others에서 랜덤 선택 확률

    def __init__(
        self,
        memory_db: MemoryDatabase,
        platform: str = 'twitter',
        core_interests: Optional[List[str]] = None,
        persona_config: Optional[Dict] = None
    ):
        super().__init__(memory_db, platform)
        self.core_interests = core_interests or []
        self.persona_config = persona_config
        self._init_scenarios()

    def _init_scenarios(self):
        """시나리오 인스턴스 초기화"""
        self.scenarios = {
            'familiar_person': FamiliarPersonScenario(self.memory_db, self.platform, self.persona_config),
            'interesting_post': InterestingPostScenario(self.memory_db, self.platform, self.persona_config)
        }

    def run(
        self,
        posts: List[Dict[str, Any]],
        process_limit: int = 1
    ) -> Optional[JourneyResult]:
        """
        피드 탐색 및 처리

        Args:
            posts: 외부에서 가져온 포스트 목록 (search_tweets 결과)
            process_limit: 처리할 포스트 수 (기본 1개)
        """
        if not posts:
            return None

        # HYBRID v1: Rule-based classification (no LLM)
        classified = self._quick_classify_hybrid(posts)

        # Priority-based selection
        selected, scenario_type = self._select_one_hybrid(classified)
        if not selected:
            return None

        return self._run_scenario(selected, scenario_type)

    def _quick_classify_hybrid(self, posts: List[Dict]) -> ClassifiedPosts:
        """
        HYBRID v1: Rule-based 분류 (LLM 없음)

        분류 기준:
        - familiar: user_id가 person_memories에 있고 tier가 familiar/friend
        - interesting: 텍스트에 core_interests 키워드 포함
        - others: 나머지
        """
        familiar = []
        interesting = []
        others = []

        for post in posts:
            user_id = post.get('user_id') or post.get('user', '')
            screen_name = post.get('user', '')

            # 1. 아는 사람인지 확인
            person = self.memory_db.get_person(user_id, self.platform)
            if person and person.tier in ('familiar', 'friend'):
                familiar.append((post, person))
                continue

            # 2. 관심 키워드 매칭
            text = post.get('text', '').lower()
            if self._matches_core_interests(text):
                interesting.append(post)
                continue

            # 3. 나머지
            others.append(post)

        return ClassifiedPosts(familiar=familiar, interesting=interesting, others=others)

    def _matches_core_interests(self, text: str) -> bool:
        """텍스트가 관심 키워드를 포함하는지 확인"""
        if not self.core_interests:
            return False
        text_lower = text.lower()
        return any(interest.lower() in text_lower for interest in self.core_interests)

    def _select_one_hybrid(
        self, classified: ClassifiedPosts
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        HYBRID v1: 우선순위 기반 1개 선택

        Priority:
        1. familiar (아는 사람) → 가장 최근 상호작용 기준
        2. interesting (관심 포스트) → 랜덤
        3. others (10% 확률) → 랜덤 발견
        """
        # 1. 아는 사람 우선
        if classified.familiar:
            post, person = self._pick_best_familiar(classified.familiar)
            return post, 'familiar_person'

        # 2. 관심 포스트
        if classified.interesting:
            post = self._pick_best_interesting(classified.interesting)
            return post, 'interesting_post'

        # 3. 랜덤 발견 (10% 확률)
        if classified.others and random.random() < self.RANDOM_DISCOVERY_PROB:
            post = random.choice(classified.others)
            return post, 'interesting_post'  # 일반 포스트도 interesting 시나리오로 처리

        return None, None

    def _pick_best_familiar(
        self, familiar_posts: List[Tuple[Dict, PersonMemory]]
    ) -> Tuple[Dict, PersonMemory]:
        """아는 사람 중 최적 선택 (affinity 높은 순)"""
        sorted_posts = sorted(
            familiar_posts,
            key=lambda x: x[1].affinity,
            reverse=True
        )
        return sorted_posts[0]

    def _pick_best_interesting(self, posts: List[Dict]) -> Dict:
        """관심 포스트 중 최적 선택 (engagement 기반)"""
        def get_score(post: Dict) -> float:
            engagement = post.get('engagement', {})
            likes = engagement.get('favorite_count', 0)
            retweets = engagement.get('retweet_count', 0)
            return likes + retweets * 2

        sorted_posts = sorted(posts, key=get_score, reverse=True)
        return sorted_posts[0]

    def _run_scenario(
        self, post: Dict, scenario_type: str
    ) -> Optional[JourneyResult]:
        """시나리오 실행"""
        scenario = self.scenarios.get(scenario_type)
        if not scenario:
            return None

        try:
            result = scenario.execute(post)
            return JourneyResult(
                success=result.success if result else False,
                scenario_executed=scenario_type,
                action_taken=result.action if result else None,
                target_user=post.get('user'),
                details=result.details if result else None
            )
        except Exception as e:
            print(f"[FeedJourney] Scenario {scenario_type} failed: {e}")
            return None
