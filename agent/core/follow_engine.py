"""
Follow Engine
사람다운 팔로우 전략 / Human-like follow behavior
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from agent.platforms.interface import SocialUser
from dataclasses import dataclass, field
import yaml
from config.settings import settings
from agent.persona.persona_loader import active_persona_name, active_persona


@dataclass
class FollowCandidate:
    user_id: str
    screen_name: str
    queued_at: datetime
    execute_at: datetime
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FollowDecision:
    should_follow: bool
    reason: str
    score: float
    delay_seconds: int = 0


class FollowEngine:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = f"personas/{active_persona_name}/behavior.yaml"
        self.config = self._load_config(config_path)
        self.daily_count = 0
        self.last_reset_date = datetime.now().date()
        self.follow_queue: List[FollowCandidate] = []
        self.followed_users: set = set()
        self.consecutive_errors = 0
        self.paused_until: Optional[datetime] = None

    def _load_config(self, path: str) -> Dict:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('follow_behavior', self._get_default_config())
        except FileNotFoundError:
            print(f"[FOLLOW] Config not found: {path}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        return {
            'enabled': True,
            'daily_limit': 20,
            'base_probability': 0.15,
            'score_threshold': 40,
            'delay': {
                'min': 30,
                'max': 300
            },
            'exclude': {
                'no_profile_image': True,
                'no_bio': True,
                'follower_ratio_below': 0.1,
                'account_age_days_below': 30,
                'following_above': 5000
            },
            'priority': {
                'follows_me': True,
                'bio_keywords': active_persona.domain.keywords if active_persona.domain else []
            },
            'rate_limit': {
                'max_consecutive': 3,
                'cooldown_minutes': 30
            },
            'emergency_stop': {
                'error_threshold': 3,
                'pause_hours': 1
            }
        }

    def _reset_daily_if_needed(self):
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_count = 0
            self.followed_users.clear()
            self.last_reset_date = today
            print("[FOLLOW] Daily reset")

    def _is_paused(self) -> bool:
        if self.paused_until and datetime.now() < self.paused_until:
            return True
        if self.paused_until and datetime.now() >= self.paused_until:
            self.paused_until = None
            self.consecutive_errors = 0
            print("[FOLLOW] Pause ended")
        return False

    def _check_eligibility(self, user: SocialUser) -> Tuple[bool, str]:
        """자격 검증"""
        exclude = self.config.get('exclude', {})

        # 이미 팔로우한 유저
        if user.id in self.followed_users:
            return False, "이미 팔로우함"

        # 프로필 이미지 없음
        if exclude.get('no_profile_image', True):
            if not user.profile_image_url or 'default' in user.profile_image_url.lower():
                return False, "프로필 이미지 없음"

        # 바이오 없음
        if exclude.get('no_bio', True):
            if not user.bio or len(user.bio.strip()) < 5:
                return False, "바이오 없음"

        # 팔로워 비율 체크
        follower_ratio_min = exclude.get('follower_ratio_below', 0.1)
        followers = user.followers_count
        following = user.following_count
        if following > 0:
            ratio = followers / following
            if ratio < follower_ratio_min:
                return False, f"팔로워 비율 낮음 ({ratio:.2f})"

        # 계정 나이 체크
        min_age_days = exclude.get('account_age_days_below', 30)
        created_at = user.created_at
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_date = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                else:
                    created_date = created_at
                age_days = (datetime.now(created_date.tzinfo) - created_date).days
                if age_days < min_age_days:
                    return False, f"계정 나이 {age_days}일 (최소 {min_age_days}일)"
            except (ValueError, TypeError):
                pass

        # 팔로잉 수 체크
        max_following = exclude.get('following_above', 5000)
        if following > max_following:
            return False, f"팔로잉 {following}명 (최대 {max_following})"

        return True, "eligible"

    def _calculate_score(self, user: SocialUser, context: Dict) -> float:
        """팔로우 점수 계산 (0-100)"""
        score = 50.0
        priority = self.config.get('priority', {})

        # 맞팔 여부
        if priority.get('follows_me', True) and user.following_me:
            score += 30

        # 바이오 키워드 매칭
        bio_keywords = priority.get('bio_keywords', [])
        bio = (user.bio or '').lower()
        for keyword in bio_keywords:
            if keyword.lower() in bio:
                score += 10

        # 상호작용 이력
        interaction_count = context.get('interaction_count', 0)
        if interaction_count > 0:
            score += min(interaction_count * 5, 20)

        # 팔로워 수 (적당히 있으면 +)
        followers = user.followers_count
        if 100 <= followers <= 10000:
            score += 10
        elif followers > 10000:
            score += 5

        # 계정 품질 (프로필 완성도)
        if user.profile_image_url and 'default' not in user.profile_image_url.lower():
            score += 5
        if user.bio:
            score += 5

        return min(100, max(0, score))

    def should_follow(self, user: SocialUser, interaction_context: Dict = None) -> FollowDecision:
        """팔로우 여부 결정"""
        if interaction_context is None:
            interaction_context = {}

        self._reset_daily_if_needed()

        # 비활성화 체크
        if not self.config.get('enabled', True):
            return FollowDecision(False, "팔로우 기능 비활성화", 0)

        # 일시정지 체크
        if self._is_paused():
            remaining = (self.paused_until - datetime.now()).seconds // 60
            return FollowDecision(False, f"일시정지 중 ({remaining}분 남음)", 0)

        # 일일 한도 체크
        daily_limit = self.config.get('daily_limit', 20)
        if self.daily_count >= daily_limit:
            return FollowDecision(False, f"일일 한도 초과 ({self.daily_count}/{daily_limit})", 0)

        # 자격 검증
        eligible, reason = self._check_eligibility(user)
        if not eligible:
            return FollowDecision(False, reason, 0)

        # 점수 계산
        score = self._calculate_score(user, interaction_context)
        threshold = self.config.get('score_threshold', 40)

        if score < threshold:
            return FollowDecision(False, f"점수 미달 ({score:.1f} < {threshold})", score)

        # 확률 결정
        base_prob = self.config.get('base_probability', 0.15)
        adjusted_prob = base_prob * (score / 50)  # 점수에 비례
        adjusted_prob = min(adjusted_prob, 0.8)

        if random.random() > adjusted_prob:
            return FollowDecision(False, f"확률 미통과 ({adjusted_prob:.1%})", score)

        # 지연 시간 계산
        delay_config = self.config.get('delay', {'min': 30, 'max': 300})
        delay_seconds = random.randint(delay_config['min'], delay_config['max'])

        return FollowDecision(
            should_follow=True,
            reason=f"점수 {score:.1f}, 확률 {adjusted_prob:.1%}",
            score=score,
            delay_seconds=delay_seconds
        )

    def queue_follow(self, user_id: str, screen_name: str, context: Dict = None):
        """지연 실행 큐에 추가"""
        if context is None:
            context = {}

        delay_config = self.config.get('delay', {'min': 30, 'max': 300})
        delay_seconds = random.randint(delay_config['min'], delay_config['max'])

        candidate = FollowCandidate(
            user_id=user_id,
            screen_name=screen_name,
            queued_at=datetime.now(),
            execute_at=datetime.now() + timedelta(seconds=delay_seconds),
            context=context
        )
        self.follow_queue.append(candidate)
        print(f"[FOLLOW] Queued @{screen_name} (execute in {delay_seconds}s)")

    def process_queue(self, follow_func) -> List[Tuple[str, bool, str]]:
        """큐 처리

        Args:
            follow_func: 실제 팔로우 실행 함수 (user_id) -> bool

        Returns:
            List of (screen_name, success, reason)
        """
        if self._is_paused():
            return []

        results = []
        now = datetime.now()
        processed_indices = []

        # Rate limit: 연속 팔로우 제한
        rate_limit = self.config.get('rate_limit', {'max_consecutive': 3, 'cooldown_minutes': 30})
        consecutive_count = 0

        for i, candidate in enumerate(self.follow_queue):
            if now < candidate.execute_at:
                continue

            if consecutive_count >= rate_limit.get('max_consecutive', 3):
                print(f"[FOLLOW] Rate limit reached, pausing queue")
                break

            try:
                success = follow_func(candidate.user_id)

                if success:
                    self.daily_count += 1
                    self.followed_users.add(candidate.user_id)
                    self.consecutive_errors = 0
                    consecutive_count += 1
                    results.append((candidate.screen_name, True, "success"))
                    print(f"[FOLLOW] @{candidate.screen_name} ({self.daily_count}/{self.config.get('daily_limit', 20)})")
                else:
                    results.append((candidate.screen_name, False, "API 실패"))
                    self._handle_error()

            except Exception as e:
                results.append((candidate.screen_name, False, str(e)))
                self._handle_error()

            processed_indices.append(i)

        # 처리된 항목 제거 (역순으로)
        for i in reversed(processed_indices):
            self.follow_queue.pop(i)

        return results

    def _handle_error(self):
        """에러 처리"""
        self.consecutive_errors += 1
        emergency = self.config.get('emergency_stop', {'error_threshold': 3, 'pause_hours': 1})

        if self.consecutive_errors >= emergency.get('error_threshold', 3):
            pause_hours = emergency.get('pause_hours', 1)
            self.paused_until = datetime.now() + timedelta(hours=pause_hours)
            print(f"[FOLLOW] Emergency stop - paused for {pause_hours}h")

    def get_queue_status(self) -> Dict:
        """큐 상태 조회"""
        return {
            'queue_size': len(self.follow_queue),
            'daily_count': self.daily_count,
            'daily_limit': self.config.get('daily_limit', 20),
            'paused': self._is_paused(),
            'paused_until': self.paused_until.isoformat() if self.paused_until else None,
            'consecutive_errors': self.consecutive_errors
        }

    def get_pending_follows(self) -> List[Dict]:
        """대기 중인 팔로우 목록"""
        return [
            {
                'screen_name': c.screen_name,
                'queued_at': c.queued_at.isoformat(),
                'execute_at': c.execute_at.isoformat(),
                'seconds_until': max(0, (c.execute_at - datetime.now()).total_seconds())
            }
            for c in self.follow_queue
        ]


# Global instance
follow_engine = FollowEngine()
