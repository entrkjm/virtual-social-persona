"""
Social Mode Engine (Session-based v3)
세션 기반 활동 - 알림/피드 배치 처리 후 휴식

사람 패턴: 폰 켜서 알림 쭉 확인 → 피드 스크롤 → 내려놓기 → 반복
"""
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable

from agent.core.logger import logger
from agent.memory.database import MemoryDatabase
from agent.memory.factory import MemoryFactory
from agent.platforms.twitter.api.social import get_tweet_replies, get_user_profile

from .journeys.notification import NotificationJourney
from .journeys.feed import FeedJourney
from .journeys.profile_visit import ProfileVisitJourney
from .journeys.base import JourneyResult


@dataclass
class SessionResult:
    """세션 실행 결과"""
    notifications_processed: int = 0
    feeds_browsed: int = 0
    feeds_reacted: int = 0
    profiles_visited: int = 0
    actions_taken: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def total_actions(self) -> int:
        return len(self.actions_taken)


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

        # 세션 설정 로드
        self.session_config = self.activity_config.get('session', {})
        self.human_like_config = self.activity_config.get('human_like', {})

        # 세션 카운터
        self.session_count = 0

        # 메모리 DB
        self.memory_db = MemoryFactory.get_memory_db(persona_id)

        # 관심 키워드 추출
        self.core_interests = self._extract_core_interests()

        # Journey 인스턴스
        self.notification_journey = NotificationJourney(
            self.memory_db, platform, persona_config
        )
        feed_cfg = self.session_config.get('feed', {})
        feed_selection = {
            'familiar_first': feed_cfg.get('familiar_first', True),
            'random_discovery_prob': feed_cfg.get('random_discovery_prob', 0.1),
            'language_filter': feed_cfg.get('language_filter')
        }
        self.feed_journey = FeedJourney(
            self.memory_db,
            platform,
            self.core_interests,
            persona_config,
            feed_selection=feed_selection
        )

        # Profile Visit Journey
        visit_cfg = self.session_config.get('profile_visit', {})
        self.profile_visit_journey = ProfileVisitJourney(
            self.memory_db,
            platform,
            persona_config,
            visit_config=visit_cfg
        )
        self.profile_visit_enabled = visit_cfg.get('enabled', False)

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

    async def session(
        self,
        get_feed_posts: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        get_following_list: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        get_user_tweets_fn: Optional[Callable] = None,
        delay_fn: Optional[Callable[[float], None]] = None
    ) -> SessionResult:
        """
        세션 실행 - 알림 처리 → 피드 탐색 → 프로필 방문 → 휴식

        Args:
            get_feed_posts: 피드 포스트 가져오는 함수 (없으면 피드 스킵)
            get_following_list: 팔로잉 목록 가져오는 함수 (없으면 프로필 방문 스킵)
            get_user_tweets_fn: 유저 트윗 가져오는 함수 (profile visit용)
            delay_fn: 딜레이 함수 (테스트용 오버라이드 가능)
        """
        start_time = time.time()
        result = SessionResult()
        self.session_count += 1

        # 워밍업 체크
        warmup_sessions = self.session_config.get('warmup_sessions', 2)
        is_warmup = self.session_count <= warmup_sessions

        if is_warmup:
            logger.info(f"[Session #{self.session_count}] Warmup mode - read only")

        # 딜레이 함수 (기본: asyncio.sleep)
        async def default_delay(seconds: float):
            await asyncio.sleep(seconds)

        do_delay = delay_fn if delay_fn else default_delay

        # 세션 내 딜레이 범위
        intra_delay = self.session_config.get('intra_delay', [2, 8])

        # Human-like 설정 로드
        reading_cfg = self.human_like_config.get('reading', {})
        thinking_cfg = self.human_like_config.get('thinking', {})
        transitions_cfg = self.human_like_config.get('transitions', {})

        # === Phase 1: 알림 처리 ===
        notif_cfg = self.session_config.get('notification', {})
        notif_count_range = notif_cfg.get('count', [3, 8])
        notif_count = random.randint(notif_count_range[0], notif_count_range[1])

        logger.info(f"[Session #{self.session_count}] Processing up to {notif_count} notifications")

        for i in range(notif_count):
            try:
                notif_result = self.run_notification_journey(process_limit=1)
                if notif_result and notif_result.success:
                    result.notifications_processed += 1
                    if not is_warmup and notif_result.action_taken:
                        result.actions_taken.append(f"notif:{notif_result.action_taken}")

                # 세션 내 딜레이
                delay = random.uniform(intra_delay[0], intra_delay[1])
                await do_delay(delay)

            except Exception as e:
                error_str = str(e).lower()
                if any(code in error_str for code in ['226', '401', '403', 'authorization']):
                    raise
                logger.warning(f"[Session] Notification error: {e}")
                break

        # === Phase 2: 피드 탐색 ===
        if get_feed_posts:
            feed_cfg = self.session_config.get('feed', {})
            browse_range = feed_cfg.get('browse_count', [5, 15])
            react_range = feed_cfg.get('react_count', [1, 3])

            browse_count = random.randint(browse_range[0], browse_range[1])
            max_reactions = random.randint(react_range[0], react_range[1])

            if is_warmup:
                logger.info(f"[Session #{self.session_count}] Browsing {browse_count} feeds (warmup, read-only)")
            else:
                logger.info(f"[Session #{self.session_count}] Browsing {browse_count} feeds, max {max_reactions} reactions")

            try:
                posts = get_feed_posts()
                posts_to_browse = []

                if not posts:
                    logger.info("[Session] No posts fetched")
                else:
                    # 배치 필터링 (LLM 1회 호출)
                    filter_results = self.feed_journey.feed_filter.filter_batch(posts)
                    passed_ids = {r.post_id for r in filter_results if r.passed}
                    filtered_posts = [p for p in posts if str(p.get('id', '')) in passed_ids]

                    filtered_out = len(posts) - len(filtered_posts)
                    if filtered_out > 0:
                        logger.info(f"[Session] Filtered out {filtered_out}/{len(posts)} posts")

                    # 우선순위 정렬 (familiar → interesting → others)
                    sorted_posts = self._sort_posts_by_priority(filtered_posts)
                    posts_to_browse = sorted_posts[:browse_count]

                reactions = 0

                # Phase 2-1: 모든 포스트 컨텍스트 수집 (author + replies)
                if not is_warmup:
                    posts_to_browse = await self._enrich_posts_context(
                        posts_to_browse, do_delay, reading_cfg, max_reactions
                    )

                    # Phase 2-2: 전체 컨텍스트 보고 반응할 포스트 선정
                    selected_posts = self._select_posts_for_reaction(
                        posts_to_browse, max_reactions
                    )
                    selected_ids = {p.get('id') for p in selected_posts}
                    logger.info(f"[Feed] Selected {len(selected_posts)} posts for reaction")
                else:
                    selected_ids = set()

                # Phase 2-3: 포스트 처리
                for post in posts_to_browse:
                    result.feeds_browsed += 1
                    user = post.get('user', 'unknown')
                    text = post.get('text', '')
                    text_preview = (text[:40] + '...') if text else ''
                    post_id = post.get('id')

                    if is_warmup:
                        logger.info(f"[Feed] @{user}: {text_preview} (warmup)")
                        scroll_delay = transitions_cfg.get('scroll_to_next', [1.0, 3.0])
                        await do_delay(random.uniform(scroll_delay[0], scroll_delay[1]))
                        continue

                    if reactions >= max_reactions:
                        logger.info(f"[Feed] @{user}: {text_preview} (max reached)")
                        scroll_delay = transitions_cfg.get('scroll_to_next', [1.0, 3.0])
                        await do_delay(random.uniform(scroll_delay[0], scroll_delay[1]))
                        continue

                    # 선정되지 않은 포스트는 스킵
                    if post_id not in selected_ids:
                        logger.info(f"[Feed] @{user}: {text_preview} (not selected)")
                        scroll_delay = transitions_cfg.get('scroll_to_next', [1.0, 3.0])
                        await do_delay(random.uniform(scroll_delay[0], scroll_delay[1]))
                        continue

                    # 생각 딜레이 (반응 전)
                    think_delay = thinking_cfg.get('before_reply', [2.0, 5.0])
                    await do_delay(random.uniform(think_delay[0], think_delay[1]))

                    feed_result = self.run_feed_journey([post], process_limit=1)
                    if feed_result and feed_result.success and feed_result.action_taken:
                        result.feeds_reacted += 1
                        result.actions_taken.append(f"feed:{feed_result.action_taken}")
                        reactions += 1
                        logger.info(f"[Feed] @{user}: {feed_result.action_taken}")
                    else:
                        logger.info(f"[Feed] @{user}: {text_preview} (skip)")

                    # 스크롤 딜레이 (다음 포스트로 이동)
                    scroll_delay = transitions_cfg.get('scroll_to_next', [1.0, 3.0])
                    await do_delay(random.uniform(scroll_delay[0], scroll_delay[1]))

            except Exception as e:
                error_str = str(e).lower()
                if any(code in error_str for code in ['226', '401', '403', 'authorization']):
                    raise
                logger.warning(f"[Session] Feed error: {e}")

        # === Phase 3: 프로필 방문 ===
        # 스킵 사유 로깅
        if not self.profile_visit_enabled:
            logger.info("[Session] ProfileVisit: disabled in config")
        elif not get_following_list:
            logger.info("[Session] ProfileVisit: no get_following_list function")
        elif not get_user_tweets_fn:
            logger.info("[Session] ProfileVisit: no get_user_tweets_fn function")
        elif is_warmup:
            logger.info("[Session] ProfileVisit: skipped (warmup mode)")
        elif self.profile_visit_enabled and get_following_list and get_user_tweets_fn and not is_warmup:
            visit_cfg = self.session_config.get('profile_visit', {})
            visit_count_range = visit_cfg.get('count', [0, 2])
            visit_count = random.randint(visit_count_range[0], visit_count_range[1])

            if visit_count == 0:
                logger.info(f"[Session] ProfileVisit: visit_count=0 (random from {visit_count_range})")
            else:
                logger.info(f"[Session #{self.session_count}] Visiting {visit_count} profiles")

                try:
                    following_list = get_following_list()
                    if not following_list:
                        logger.info("[ProfileVisit] No following list returned")
                    else:
                        for _ in range(visit_count):
                            # 탭 전환 딜레이
                            switch_delay = transitions_cfg.get('switch_tab', [2.0, 5.0])
                            await do_delay(random.uniform(switch_delay[0], switch_delay[1]))

                            visit_result = self.profile_visit_journey.run(
                                following_list=following_list,
                                get_user_tweets_fn=get_user_tweets_fn,
                                process_limit=1
                            )

                            if visit_result:
                                result.profiles_visited += 1
                                if visit_result.action_taken:
                                    result.actions_taken.append(f"visit:{visit_result.action_taken}")
                                    logger.info(f"[ProfileVisit] @{visit_result.target_user}: {visit_result.action_taken}")
                                else:
                                    logger.info(f"[ProfileVisit] @{visit_result.target_user}: no action")

                            # 프로필 간 딜레이
                            await do_delay(random.uniform(intra_delay[0], intra_delay[1]))

                except Exception as e:
                    error_str = str(e).lower()
                    if any(code in error_str for code in ['226', '401', '403', 'authorization']):
                        raise
                    logger.warning(f"[Session] Profile visit error: {e}")

        result.duration_seconds = time.time() - start_time
        logger.info(
            f"[Session #{self.session_count}] Done: "
            f"{result.notifications_processed} notifs, "
            f"{result.feeds_browsed} browsed, "
            f"{result.feeds_reacted} reacted, "
            f"{result.profiles_visited} visited, "
            f"{result.total_actions} actions in {result.duration_seconds:.1f}s"
        )

        return result

    def _sort_posts_by_priority(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        포스트를 우선순위로 정렬: familiar → interesting → others
        """
        familiar = []
        interesting = []
        others = []

        for post in posts:
            user_id = post.get('user_id') or post.get('user', '')
            text = post.get('text', '').lower()

            # 1. 아는 사람 체크
            person = self.memory_db.get_person(user_id, self.platform)
            if person and person.tier in ('familiar', 'friend'):
                familiar.append(post)
                continue

            # 2. 관심 키워드 매칭
            if any(kw.lower() in text for kw in self.core_interests):
                interesting.append(post)
                continue

            # 3. 나머지
            others.append(post)

        sorted_posts = familiar + interesting + others
        if familiar or interesting:
            logger.info(f"[Session] Posts sorted: {len(familiar)} familiar, {len(interesting)} interesting, {len(others)} others")
        return sorted_posts

    def _calc_reading_delay(self, text: str, reading_cfg: Dict) -> float:
        """텍스트 길이 기반 읽기 시간 계산"""
        chars_per_sec = reading_cfg.get('chars_per_second', 5)
        min_delay = reading_cfg.get('min', 1.0)
        max_delay = reading_cfg.get('max', 8.0)
        variance = reading_cfg.get('variance', 0.3)

        base = len(text) / chars_per_sec
        varied = base * (1 + random.uniform(-variance, variance))
        return max(min_delay, min(max_delay, varied))

    async def _enrich_posts_context(
        self,
        posts: List[Dict[str, Any]],
        do_delay,
        reading_cfg: Dict,
        max_count: int
    ) -> List[Dict[str, Any]]:
        """
        포스트별 컨텍스트 수집 (author_profile + replies)
        human-like 딜레이 포함
        """
        enriched = []
        for i, post in enumerate(posts[:max_count * 2]):  # 선정 후보 2배까지만 수집
            user = post.get('user', 'unknown')
            text = post.get('text', '')
            post_id = post.get('id')

            # 읽기 딜레이
            if reading_cfg and text:
                read_delay = self._calc_reading_delay(text, reading_cfg)
                logger.info(f"[Feed] Reading @{user}'s post ({read_delay:.1f}s)")
                await do_delay(read_delay)

            # 글쓴이 프로필 가져오기
            try:
                user_id = post.get('user_id')
                screen_name = post.get('user')
                if user_id or screen_name:
                    author_profile = get_user_profile(user_id=user_id, screen_name=screen_name)
                    if author_profile:
                        post['author_profile'] = author_profile
                        bio_preview = (author_profile.get('bio', '') or '')[:30]
                        logger.info(f"[Feed] Author: @{screen_name} - {bio_preview}...")
                        await do_delay(random.uniform(1.0, 2.0))
            except Exception as e:
                logger.debug(f"[Feed] Failed to get author profile: {e}")

            # 댓글 가져오기
            if post_id:
                try:
                    replies = get_tweet_replies(str(post_id))
                    if replies:
                        logger.info(f"[Feed] Reading {len(replies)} replies...")
                        replies_delay = min(len(replies) * random.uniform(1.0, 2.0), 8.0)
                        await do_delay(replies_delay)
                        post['replies'] = replies
                except Exception as e:
                    logger.debug(f"[Feed] Failed to get replies: {e}")

            enriched.append(post)

        return enriched

    def _select_posts_for_reaction(
        self,
        posts: List[Dict[str, Any]],
        max_reactions: int
    ) -> List[Dict[str, Any]]:
        """
        컨텍스트 기반 반응할 포스트 선정
        점수 = author_score + content_score + engagement_score
        """
        scored_posts = []

        for post in posts:
            score = 0.0
            user_id = post.get('user_id') or post.get('user', '')
            text = post.get('text', '').lower()
            author_profile = post.get('author_profile', {})
            replies = post.get('replies', [])

            # 1. Author Score (0-40점)
            # 아는 사람이면 가산
            person = self.memory_db.get_person(user_id, self.platform)
            if person and person.tier == 'friend':
                score += 40
            elif person and person.tier == 'familiar':
                score += 30

            # 프로필 완성도 (bio 있으면)
            if author_profile.get('bio'):
                score += 5
            # 팔로워 수 (신뢰도)
            followers = author_profile.get('followers_count', 0)
            if followers > 1000:
                score += 5
            elif followers > 100:
                score += 2

            # 2. Content Score (0-30점)
            # 관심 키워드 매칭
            matching_interests = sum(1 for kw in self.core_interests if kw.lower() in text)
            score += min(matching_interests * 10, 30)

            # 3. Engagement Score (0-20점)
            engagement = post.get('engagement', {})
            likes = engagement.get('favorite_count', 0)
            retweets = engagement.get('retweet_count', 0)
            engagement_score = min((likes + retweets * 2) / 10, 20)
            score += engagement_score

            # 4. Reply Context Score (0-10점)
            # 댓글이 적으면 참여 기회 높음
            if replies:
                if len(replies) < 3:
                    score += 10
                elif len(replies) < 10:
                    score += 5
            else:
                score += 8  # 댓글 없으면 첫 댓글 기회

            scored_posts.append((post, score))

        # 점수순 정렬
        scored_posts.sort(key=lambda x: x[1], reverse=True)

        selected = [p for p, s in scored_posts[:max_reactions]]
        if selected:
            top_scores = [f"@{p.get('user')}({s:.0f})" for p, s in scored_posts[:max_reactions]]
            logger.info(f"[Feed] Selection scores: {', '.join(top_scores)}")

        return selected

    def get_session_interval(self) -> tuple[int, int]:
        """세션 간 휴식 시간 반환 (초)"""
        interval = self.session_config.get('interval', [1800, 7200])
        return interval[0], interval[1]

    def is_warmup(self) -> bool:
        """현재 워밍업 상태인지"""
        warmup_sessions = self.session_config.get('warmup_sessions', 2)
        return self.session_count < warmup_sessions
