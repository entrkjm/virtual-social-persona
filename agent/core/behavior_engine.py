"""
Behavior Engine
확률 기반 판단 / 기분 변동 / 현타 시스템
Probabilistic decision-making with mood & regret
"""
import yaml
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from config.settings import settings
from agent.persona.persona_loader import active_persona_name
from agent.core.mode_manager import mode_manager


@dataclass
class BehaviorDecision:
    decision: str  # "INTERACT" or "SKIP"
    reason: str
    suggested_action: str  # "LURK", "LIKE", "COMMENT", "LIKE_AND_COMMENT"
    confidence: float
    mood_state: float


@dataclass
class HumanLikeState:
    step_count: int = 0
    session_action_count: int = 0
    consecutive_action_count: int = 0
    last_action_time: Optional[datetime] = None
    last_action_type: Optional[str] = None
    action_history: List[Tuple[str, datetime]] = field(default_factory=list)
    error_226_until: Optional[datetime] = None
    error_404_until: Optional[datetime] = None
    probability_modifier: float = 1.0


class HumanLikeController:
    """Human-like 행동 패턴 제어 (워밍업, 지연, 버스트 방지, 에러 핸들링)"""

    def __init__(self, config: Dict):
        self.config = config.get('human_like', {})
        self.state = HumanLikeState()

    def _get_warmup_config(self) -> Dict:
        return self.config.get('warmup', {'enabled': True, 'steps': 5})

    def _get_delay_config(self) -> Dict:
        return self.config.get('action_delays', {
            'after_like': [2, 5],
            'after_comment': [5, 15],
            'after_post': [30, 120],
            'between_steps': [3, 10]
        })

    def _get_burst_config(self) -> Dict:
        return self.config.get('burst_prevention', {
            'max_consecutive_actions': 3,
            'cooldown_after_burst': 60
        })

    def _get_error_config(self) -> Dict:
        return self.config.get('error_handling', {
            'on_226': {'pause_minutes': 30, 'reduce_probability': 0.5},
            'on_404': {'pause_minutes': 5}
        })

    def increment_step(self):
        self.state.step_count += 1

    def is_in_warmup(self) -> bool:
        warmup_steps = mode_manager.config.warmup_steps
        return self.state.step_count < warmup_steps

    def is_paused_for_error(self) -> Tuple[bool, Optional[str]]:
        now = datetime.now()
        if self.state.error_226_until and now < self.state.error_226_until:
            remaining = (self.state.error_226_until - now).total_seconds() / 60
            return True, f"226 에러로 인한 일시정지 (남은 시간: {remaining:.1f}분)"
        if self.state.error_404_until and now < self.state.error_404_until:
            remaining = (self.state.error_404_until - now).total_seconds() / 60
            return True, f"404 에러로 인한 일시정지 (남은 시간: {remaining:.1f}분)"
        return False, None

    def is_in_burst_cooldown(self) -> bool:
        burst = self._get_burst_config()
        max_consecutive = burst.get('max_consecutive_actions', 3)
        if self.state.consecutive_action_count >= max_consecutive:
            cooldown = burst.get('cooldown_after_burst', 60)
            if self.state.last_action_time:
                elapsed = (datetime.now() - self.state.last_action_time).total_seconds()
                if elapsed < cooldown:
                    return True
                else:
                    self.state.consecutive_action_count = 0
        return False

    def get_probability_modifier(self) -> float:
        return self.state.probability_modifier

    def apply_action_delay(self, action_type: str):
        delays = self._get_delay_config()
        delay_range = None

        if action_type == 'like':
            delay_range = delays.get('after_like', [2, 5])
        elif action_type in ('comment', 'reply'):
            delay_range = delays.get('after_comment', [5, 15])
        elif action_type == 'post':
            delay_range = delays.get('after_post', [30, 120])

        if delay_range:
            delay = random.uniform(delay_range[0], delay_range[1])
            print(f"[HUMAN-LIKE] {action_type} 후 {delay:.1f}초 대기...")
            time.sleep(delay)

    def apply_between_actions_delay(self):
        delays = self._get_delay_config()
        delay_range = delays.get('between_steps', [3, 10])
        delay = random.uniform(delay_range[0], delay_range[1])
        print(f"[HUMAN-LIKE] 액션 간 {delay:.1f}초 대기...")
        time.sleep(delay)

    def record_action(self, action_type: str):
        now = datetime.now()
        self.state.session_action_count += 1
        self.state.consecutive_action_count += 1
        self.state.last_action_time = now
        self.state.last_action_type = action_type
        self.state.action_history.append((action_type, now))

        if len(self.state.action_history) > 100:
            self.state.action_history = self.state.action_history[-50:]

    def handle_error(self, error_code: int):
        error_cfg = self._get_error_config()
        now = datetime.now()

        if error_code == 226:
            cfg = error_cfg.get('on_226', {})
            pause_minutes = cfg.get('pause_minutes', 30)
            reduce_prob = cfg.get('reduce_probability', 0.5)
            self.state.error_226_until = now + timedelta(minutes=pause_minutes)
            self.state.probability_modifier *= reduce_prob
            print(f"[HUMAN-LIKE] 226 에러 감지. {pause_minutes}분 정지, 확률 {reduce_prob}배 감소")

        elif error_code == 404:
            cfg = error_cfg.get('on_404', {})
            pause_minutes = cfg.get('pause_minutes', 5)
            self.state.error_404_until = now + timedelta(minutes=pause_minutes)
            print(f"[HUMAN-LIKE] 404 에러 감지. {pause_minutes}분 정지")

    def can_take_action(self) -> Tuple[bool, Optional[str]]:
        if self.is_in_warmup():
            remaining = self._get_warmup_config().get('steps', 5) - self.state.step_count
            return False, f"워밍업 중 (남은 스텝: {remaining})"

        paused, reason = self.is_paused_for_error()
        if paused:
            return False, reason

        if self.is_in_burst_cooldown():
            return False, "연속 액션 제한 (쿨다운 중)"

        return True, None

    def get_status(self) -> Dict:
        return {
            'step_count': self.state.step_count,
            'session_action_count': self.state.session_action_count,
            'consecutive_action_count': self.state.consecutive_action_count,
            'is_warmup': self.is_in_warmup(),
            'is_burst_cooldown': self.is_in_burst_cooldown(),
            'probability_modifier': self.state.probability_modifier
        }


class BehaviorEngine:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = f"config/personas/{active_persona_name}/behavior.yaml"
        self.config = self._load_config(config_path)
        self.current_mood = self.config.get('interaction_patterns', {}).get(
            'mood_volatility', {}
        ).get('base_mood', 0.5)
        self.daily_interaction_count = 0
        self.last_reset_date = datetime.now().date()
        self.user_interaction_history: Dict[str, List[datetime]] = {}
        self.post_comment_history: Dict[str, int] = {}

    def _load_config(self, path: str) -> Dict:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"[BEHAVIOR] Config not found: {path}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        return {
            'personality_traits': {
                'introversion': 0.85,
                'impulsiveness': 0.15,
                'obsessiveness': 0.80,
                'curiosity': 0.60
            },
            'interaction_patterns': {
                'same_user': {
                    'max_interactions_per_day': 3,
                    'cooldown_minutes': 120,
                    'obsession_override': True,
                    'obsession_topics': ['요리', '레시피']
                },
                'same_post': {
                    'max_comments_per_post': 2,
                    'regret_probability': settings.PROB_REGRET
                },
                'independent_actions': {
                    'like_probability': 0.30,
                    'repost_probability': 0.10,
                    'comment_probability': 0.05
                }
            }
        }

    def _reset_daily_counters_if_needed(self):
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_interaction_count = 0
            self.user_interaction_history.clear()
            self.post_comment_history.clear()
            self.last_reset_date = today

    def _count_user_interactions_today(self, user_handle: str) -> int:
        if user_handle not in self.user_interaction_history:
            return 0
        today = datetime.now().date()
        return sum(
            1 for dt in self.user_interaction_history[user_handle]
            if dt.date() == today
        )

    def _get_last_interaction_time(self, user_handle: str) -> Optional[datetime]:
        if user_handle not in self.user_interaction_history:
            return None
        if not self.user_interaction_history[user_handle]:
            return None
        return max(self.user_interaction_history[user_handle])

    def _is_in_cooldown(self, user_handle: str) -> bool:
        last_time = self._get_last_interaction_time(user_handle)
        if last_time is None:
            return False
        cooldown_minutes = self.config.get('interaction_patterns', {}).get(
            'same_user', {}
        ).get('cooldown_minutes', 120)
        return datetime.now() - last_time < timedelta(minutes=cooldown_minutes)

    def _is_obsession_topic(self, topics: List[str]) -> bool:
        obsession_topics = self.config.get('interaction_patterns', {}).get(
            'same_user', {}
        ).get('obsession_topics', [])
        topics_lower = [t.lower() for t in topics]
        for obsession in obsession_topics:
            if obsession.lower() in topics_lower or any(
                obsession.lower() in t for t in topics_lower
            ):
                return True
        return False

    def _get_post_comment_count(self, post_id: str) -> int:
        return self.post_comment_history.get(post_id, 0)

    def _calculate_time_mood_factor(self) -> float:
        hour = datetime.now().hour
        schedule = self.config.get('interaction_patterns', {}).get(
            'mood_volatility', {}
        ).get('factors', {}).get('time_of_day', {}).get('schedule', {})

        if 6 <= hour < 11:
            return schedule.get('morning', 0.4)
        elif 11 <= hour < 14:
            return schedule.get('lunch', 0.3)
        elif 14 <= hour < 17:
            return schedule.get('afternoon', 0.6)
        elif 17 <= hour < 21:
            return schedule.get('dinner', 0.5)
        else:
            return schedule.get('late_night', 0.7)

    def _calculate_current_mood(self, context: Dict) -> float:
        mood_config = self.config.get('interaction_patterns', {}).get(
            'mood_volatility', {}
        )
        if not mood_config.get('enabled', True):
            return 0.5

        factors = mood_config.get('factors', {})
        mood = mood_config.get('base_mood', 0.5)

        # 시간대 영향
        time_impact = factors.get('time_of_day', {}).get('impact', 0.3)
        time_factor = self._calculate_time_mood_factor()
        mood += (time_factor - 0.5) * time_impact

        # 최근 상호작용 영향
        interaction_impact = factors.get('recent_interactions', {}).get('impact', 0.4)
        recent_sentiment = context.get('recent_sentiment', 'neutral')
        if recent_sentiment == 'positive':
            boost = factors.get('recent_interactions', {}).get('positive_boost', 0.2)
            mood += boost * interaction_impact
        elif recent_sentiment == 'negative':
            drop = factors.get('recent_interactions', {}).get('negative_drop', 0.3)
            mood -= drop * interaction_impact

        # 랜덤 변동
        random_impact = factors.get('random', {}).get('impact', 0.3)
        variance = factors.get('random', {}).get('variance', 0.2)
        mood += (random.random() - 0.5) * variance * random_impact

        self.current_mood = max(0.0, min(1.0, mood))
        return self.current_mood

    def _get_relationship_factor(self, relationship_context: str) -> float:
        rules = self.config.get('behavioral_rules', {})

        if '처음 보는 사람' in relationship_context or '초면' in relationship_context:
            return rules.get('when_stranger', {}).get('probability_multiplier', 0.7)

        familiar_threshold = rules.get('when_familiar', {}).get('threshold_interactions', 5)
        # relationship_context에서 상호작용 횟수 파싱 시도
        if '상호작용 횟수:' in relationship_context:
            try:
                count_str = relationship_context.split('상호작용 횟수:')[1].split('회')[0].strip()
                count = int(count_str)
                if count >= familiar_threshold:
                    return rules.get('when_familiar', {}).get('probability_multiplier', 1.3)
            except (ValueError, IndexError):
                pass

        return 1.0

    def _get_sentiment_factor(self, sentiment: str) -> float:
        rules = self.config.get('behavioral_rules', {})

        if sentiment == 'positive':
            return rules.get('when_praised', {}).get('probability_multiplier', 0.5)
        elif sentiment == 'negative':
            return rules.get('when_criticized', {}).get('probability_multiplier', 0.3)
        return 1.0

    def _get_topic_factor(self, topics: List[str]) -> float:
        if self._is_obsession_topic(topics):
            return self.config.get('behavioral_rules', {}).get(
                'when_topic_matches_obsession', {}
            ).get('probability_multiplier', 2.0)
        return 1.0

    def _get_fatigue_factor(self) -> float:
        rules = self.config.get('behavioral_rules', {})
        threshold = rules.get('when_tired', {}).get('threshold_interactions', 10)

        if self.daily_interaction_count >= threshold:
            return rules.get('when_tired', {}).get('probability_multiplier', 0.6)
        return 1.0

    def _check_regret(self, post_id: str) -> bool:
        comment_count = self._get_post_comment_count(post_id)
        if comment_count == 0:
            return False

        regret_prob = self.config.get('interaction_patterns', {}).get(
            'same_post', {}
        ).get('regret_probability', 0.3)

        return random.random() < regret_prob

    def calculate_interaction_probability(self, context: Dict) -> float:
        self._reset_daily_counters_if_needed()

        user_handle = context.get('tweet', {}).get('user', '')
        post_id = context.get('tweet', {}).get('id', '')
        topics = context.get('perception', {}).get('topics', [])
        sentiment = context.get('perception', {}).get('sentiment', 'neutral')
        relationship = context.get('relationship', '')

        from agent.core.mode_manager import AgentMode
        if mode_manager.mode == AgentMode.AGGRESSIVE:
            base_prob = 0.95
        elif mode_manager.mode == AgentMode.TEST:
            base_prob = 0.75
        else:
            base_prob = 0.5

        # 1. 같은 유저 체크
        same_user_config = self.config.get('interaction_patterns', {}).get('same_user', {})
        max_per_day = same_user_config.get('max_interactions_per_day', 3)
        user_count = self._count_user_interactions_today(user_handle)

        if user_count >= max_per_day:
            if not (same_user_config.get('obsession_override', True) and
                    self._is_obsession_topic(topics)):
                return 0.05  # 거의 스킵

        # 2. 쿨다운 체크
        if self._is_in_cooldown(user_handle):
            if not (same_user_config.get('obsession_override', True) and
                    self._is_obsession_topic(topics)):
                base_prob *= 0.3

        # 3. 같은 게시물 댓글 수 체크
        same_post_config = self.config.get('interaction_patterns', {}).get('same_post', {})
        max_comments = same_post_config.get('max_comments_per_post', 2)
        comment_count = self._get_post_comment_count(post_id)

        if comment_count >= max_comments:
            return 0.0  # 하드 리밋

        # 4. 현타 체크
        if self._check_regret(post_id):
            return 0.0  # 현타 발동

        # 5. 기분 반영
        context['recent_sentiment'] = sentiment
        mood = self._calculate_current_mood(context)
        base_prob *= (0.5 + mood * 0.5)

        # 6. 관계 반영
        relationship_factor = self._get_relationship_factor(relationship)
        base_prob *= relationship_factor

        # 7. 감정 반영
        sentiment_factor = self._get_sentiment_factor(sentiment)
        base_prob *= sentiment_factor

        # 8. 주제 관심도
        topic_factor = self._get_topic_factor(topics)
        base_prob *= topic_factor

        # 9. 피로도 반영
        fatigue_factor = self._get_fatigue_factor()
        base_prob *= fatigue_factor

        # 10. 내향성 반영
        introversion = self.config.get('personality_traits', {}).get('introversion', 0.85)
        base_prob *= (1.0 - introversion * 0.5)

        return min(max(base_prob, 0.0), 1.0)

    def decide_action_type(self) -> str:
        """Deprecated: 하위 호환용. decide_actions() 사용 권장"""
        actions = self.decide_actions()
        if actions['comment']:
            return "LIKE_AND_COMMENT" if actions['like'] else "COMMENT"
        if actions['like']:
            return "LIKE"
        return "LURK"

    def decide_actions(
        self,
        perception: Optional[Dict] = None,
        tweet: Optional[Dict] = None
    ) -> Dict[str, bool]:
        """각 행동을 독립 확률로 판단 (관련도/인기도 기반 조정)

        - normal 모드: 페르소나 behavior.yaml 값 사용
        - test/aggressive 모드: mode_manager 오버라이드 값 사용
        - perception/tweet 전달 시 관련도/인기도 기반 확률 조정

        Args:
            perception: perceive_tweet 결과 (relevance_to_cooking 등)
            tweet: 트윗 데이터 (engagement 포함)

        Returns:
            {'like': bool, 'repost': bool, 'comment': bool}
        """
        if mode_manager.should_override_probabilities():
            mode_cfg = mode_manager.config
            base_like = mode_cfg.like_probability
            base_repost = mode_cfg.repost_probability
            base_comment = mode_cfg.comment_probability
        else:
            action_config = self.config.get('interaction_patterns', {}).get('independent_actions', {})
            base_like = action_config.get('like_probability', 0.30)
            base_repost = action_config.get('repost_probability', 0.10)
            base_comment = action_config.get('comment_probability', 0.05)

        # 관련도 기반 조정 (0.3 ~ 1.0)
        relevance = perception.get('relevance_to_cooking', 0.5) if perception else 0.5
        relevance_factor = 0.3 + (relevance * 0.7)

        # 인기도 기반 조정 (engagement)
        engagement = tweet.get('engagement', {}) if tweet else {}
        likes = engagement.get('favorite_count', 0)
        retweets = engagement.get('retweet_count', 0)
        # 20개 기준 정규화, 최소 0.5
        popularity_factor = min(1.0, 0.5 + (likes + retweets * 2) / 40)

        # 최종 확률 계산
        like_prob = base_like * relevance_factor
        # repost는 관련도 + 인기도 둘 다 반영 (더 엄격)
        repost_prob = base_repost * relevance_factor * popularity_factor
        # comment는 관련도만 반영
        comment_prob = base_comment * relevance_factor

        # repost 최소 관련도 임계값 (0.4 미만이면 repost 안 함)
        if relevance < 0.4:
            repost_prob = 0

        return {
            'like': random.random() < like_prob,
            'repost': random.random() < repost_prob,
            'comment': random.random() < comment_prob
        }

    def should_interact(self, context: Dict) -> BehaviorDecision:
        self._reset_daily_counters_if_needed()

        user_handle = context.get('tweet', {}).get('user', '')
        post_id = context.get('tweet', {}).get('id', '')
        topics = context.get('perception', {}).get('topics', [])

        # 확률 계산
        probability = self.calculate_interaction_probability(context)

        # 결정
        if random.random() > probability:
            # 스킵 이유 결정
            reason = self._get_skip_reason(context, probability)
            return BehaviorDecision(
                decision="SKIP",
                reason=reason,
                suggested_action="LURK",
                confidence=1.0 - probability,
                mood_state=self.current_mood
            )

        # 상호작용하기로 결정 (suggested_action은 레거시, bot.py에서 decide_actions() 직접 사용)
        suggested_action = "INTERACT"

        # 집착 주제면 더 적극적으로
        if self._is_obsession_topic(topics) and suggested_action == "LURK":
            suggested_action = "LIKE"
        if self._is_obsession_topic(topics) and suggested_action == "LIKE":
            if random.random() < 0.5:
                suggested_action = "COMMENT"

        reason = self._get_interact_reason(context, probability, suggested_action)

        return BehaviorDecision(
            decision="INTERACT",
            reason=reason,
            suggested_action=suggested_action,
            confidence=probability,
            mood_state=self.current_mood
        )

    def _get_skip_reason(self, context: Dict, probability: float) -> str:
        user_handle = context.get('tweet', {}).get('user', '')
        post_id = context.get('tweet', {}).get('id', '')

        if self._get_post_comment_count(post_id) >= 2:
            return "이미 이 글에 충분히 댓글을 달았음"

        if self._check_regret(post_id):
            return "현타... 너무 많이 댓글 단 것 같음"

        user_count = self._count_user_interactions_today(user_handle)
        max_per_day = self.config.get('interaction_patterns', {}).get(
            'same_user', {}
        ).get('max_interactions_per_day', 3)
        if user_count >= max_per_day:
            return f"오늘 @{user_handle}와 이미 {user_count}번 대화함"

        if self._is_in_cooldown(user_handle):
            return f"@{user_handle}와 대화한 지 얼마 안 됨"

        if self.current_mood < 0.3:
            return "기분이 좋지 않음... 조용히 있고 싶음"

        if self.daily_interaction_count >= 10:
            return "오늘 너무 많이 활동함, 지침"

        return "그냥... 지나가고 싶음"

    def _get_interact_reason(self, context: Dict, probability: float, action: str) -> str:
        topics = context.get('perception', {}).get('topics', [])

        if self._is_obsession_topic(topics):
            return f"관심 주제 발견! ({', '.join(topics[:2])})"

        if self.current_mood > 0.7:
            return "기분이 좋아서 말 걸고 싶음"

        if action == "LIKE":
            return "말은 못하겠고... 좋아요만"

        return "흥미로운 글이라 반응하고 싶음"

    def record_interaction(self, user_handle: str, post_id: str, action: str):
        self._reset_daily_counters_if_needed()

        if user_handle not in self.user_interaction_history:
            self.user_interaction_history[user_handle] = []
        self.user_interaction_history[user_handle].append(datetime.now())

        if action in ["COMMENT", "LIKE_AND_COMMENT", "REPLY", "LIKE_REPLY"]:
            self.post_comment_history[post_id] = self.post_comment_history.get(post_id, 0) + 1

        self.daily_interaction_count += 1

    def update_mood_from_response(self, sentiment: str):
        factors = self.config.get('interaction_patterns', {}).get(
            'mood_volatility', {}
        ).get('factors', {}).get('recent_interactions', {})

        if sentiment == 'positive':
            boost = factors.get('positive_boost', 0.2)
            self.current_mood = min(1.0, self.current_mood + boost)
        elif sentiment == 'negative':
            drop = factors.get('negative_drop', 0.3)
            self.current_mood = max(0.0, self.current_mood - drop)

    def get_mood_description(self) -> str:
        if self.current_mood >= 0.8:
            return "기분 좋음, 활발함"
        elif self.current_mood >= 0.6:
            return "평온함"
        elif self.current_mood >= 0.4:
            return "보통"
        elif self.current_mood >= 0.2:
            return "약간 우울함"
        else:
            return "힘듦, 조용히 있고 싶음"


# Global instances
behavior_engine = BehaviorEngine()
human_like_controller = HumanLikeController(behavior_engine.config)
