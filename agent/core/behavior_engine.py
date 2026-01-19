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
from agent.persona.persona_loader import active_persona_name, active_persona
from agent.core.mode_manager import mode_manager, AgentMode


@dataclass
class BehaviorDecision:
    decision: str  # "INTERACT" or "SKIP"
    reason: str
    suggested_action: str  # "LURK", "LIKE", "COMMENT", "LIKE_AND_COMMENT"
    confidence: float
    mood_state: float
    actions: Dict[str, bool] = field(default_factory=dict)


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
            config_path = f"personas/{active_persona_name}/behavior.yaml"
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
                    'obsession_topics': active_persona.domain.keywords[:2] if active_persona.domain else []
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

    def calculate_interaction_score(self, context: Dict) -> float:
        """Calculate additive interaction score (0.0 to 1.0)"""
        self._reset_daily_counters_if_needed()

        user_handle = context.get('tweet', {}).get('user', '')
        topics = context.get('perception', {}).get('topics', [])
        sentiment = context.get('perception', {}).get('sentiment', 'neutral')
        relationship = context.get('relationship', '')

        # 1. Load Config
        model_config = self.config.get('probability_model', {})
        base_prob = model_config.get('base_probability', 0.5)
        modifiers = model_config.get('modifiers', {})

        score = base_prob
        log_factors = []

        # 2. Hard Limits (Override Score)
        # Same User Limit
        same_user_config = self.config.get('interaction_patterns', {}).get('same_user', {})
        max_per_day = same_user_config.get('max_interactions_per_day', 3)
        user_count = self._count_user_interactions_today(user_handle)
        
        is_obsession = self._is_obsession_topic(topics)
        
        if user_count >= max_per_day:
            if not (same_user_config.get('obsession_override', True) and is_obsession):
                return 0.05  # Almost zero chance if limit reached

        # Cooldown
        if self._is_in_cooldown(user_handle):
             if not (same_user_config.get('obsession_override', True) and is_obsession):
                return 0.1 # Significant drop

        # Relevance Logic (Soft Filter)
        relevance = context.get('perception', {}).get('relevance_to_domain', 1.0)
        # 0.5 + 0.5 * 0.0 (irrelevant) = 0.5x penalty
        # 0.5 + 0.5 * 1.0 (relevant) = 1.0x (no penalty)
        relevance_modifier = 0.5 + (0.5 * relevance)
        score *= relevance_modifier
        log_factors.append(f"Relevance({relevance:.2f}→x{relevance_modifier:.2f})")

        # 3. Apply Modifiers (Additive)
        
        # Mode Modifier
        from agent.core.mode_manager import AgentMode, mode_manager
        if mode_manager.mode == AgentMode.AGGRESSIVE:
            mod = modifiers.get('aggressive_mode', 0.3)
            score += mod
            log_factors.append(f"Aggressive({mod:+.2f})")

        # Obsession
        if is_obsession:
            mod = modifiers.get('obsession', 0.3)
            score += mod
            log_factors.append(f"Obsession({mod:+.2f})")

        # Sentiment
        if sentiment == 'positive':
            mod = modifiers.get('praise', 0.15)
            score += mod
            log_factors.append(f"Praise({mod:+.2f})")
        elif sentiment == 'negative':
            mod = modifiers.get('criticism', -0.20)
            score += mod
            log_factors.append(f"Criticism({mod:+.2f})")

        # Relationship
        if relationship == 'stranger':
            mod = modifiers.get('stranger', -0.10)
            score += mod
            log_factors.append(f"Stranger({mod:+.2f})")

        # Introversion (Applied if not obsession)
        if not is_obsession:
            mod = modifiers.get('introversion', -0.10)
            score += mod
            log_factors.append(f"Introversion({mod:+.2f})")

        # Clamp Score
        final_score = min(max(score, 0.0), 1.0)
        
        if mode_manager.mode == AgentMode.AGGRESSIVE or final_score > 0.5:
             print(f"[SCORE] Base:{base_prob:.2f} + {' '.join(log_factors)} = {final_score:.2f}")

        return final_score

    def calculate_interaction_probability(self, context: Dict) -> float:
        """Alias for backward compatibility"""
        return self.calculate_interaction_score(context)

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
        tweet: Optional[Dict] = None,
        interaction_score: float = 0.5
    ) -> Dict[str, bool]:
        """점수 기반 행동 결정 (Cascading Ratios)"""
        
        # Load Ratios
        model_config = self.config.get('probability_model', {})
        ratios = model_config.get('action_ratios', {'like': 1.0, 'repost': 0.8, 'comment': 0.6})
        
        # Calculate Action Probabilities
        like_prob = interaction_score * ratios.get('like', 1.0)
        repost_prob = interaction_score * ratios.get('repost', 0.8)
        comment_prob = interaction_score * ratios.get('comment', 0.6)

        # Clamp
        like_prob = min(max(like_prob, 0.0), 1.0)
        repost_prob = min(max(repost_prob, 0.0), 1.0)
        comment_prob = min(max(comment_prob, 0.0), 1.0)

        from agent.core.mode_manager import AgentMode, mode_manager
        if mode_manager.mode == AgentMode.AGGRESSIVE:
             print(f"[DECIDE] Score:{interaction_score:.2f} -> Like:{like_prob:.2f} Repost:{repost_prob:.2f} Comment:{comment_prob:.2f}")

        return {
            'like': random.random() < like_prob,
            'repost': random.random() < repost_prob,
            'comment': random.random() < comment_prob
        }

    def should_interact(self, context: Dict) -> BehaviorDecision:
        self._reset_daily_counters_if_needed()

        topics = context.get('perception', {}).get('topics', [])
        
        # Score Calculation
        score = self.calculate_interaction_score(context)

        # Binary Decision based on Score vs Random
        if random.random() > score:
            reason = self._get_skip_reason(context, score)
            return BehaviorDecision(
                decision="SKIP",
                reason=reason,
                suggested_action="LURK",
                confidence=1.0 - score,
                mood_state=self.current_mood
            )

        # Action Decision
        actions = self.decide_actions(interaction_score=score)
        
        # Backward compatibility for suggested_action string
        suggested_action = "INTERESTED"
        if actions['comment']: suggested_action = "COMMENT"
        elif actions['repost']: suggested_action = "REPOST"
        elif actions['like']: suggested_action = "LIKE"

        return BehaviorDecision(
            decision="INTERACT",
            reason=f"Score {score:.2f} passed threshold",
            suggested_action=suggested_action,
            confidence=score,
            mood_state=self.current_mood,
            actions=actions
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
