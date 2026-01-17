"""
Tier Manager
영감 티어 승격/강등 및 강도 계산
Inspiration tier promotion/demotion and strength calculation
"""
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from agent.memory.database import Inspiration, CoreMemory, generate_id


@dataclass
class TierConfig:
    decay_rate_per_day: float  # 하루당 감쇠율 (1.0 = 감쇠 없음)
    promotion_threshold_strength: Optional[float]  # 강도 기반 승격 임계값
    promotion_threshold_reinforcement: Optional[int]  # 강화 횟수 기반 승격 임계값
    demotion_threshold: float  # 이 강도 이하면 강등
    max_count: Optional[int]  # 최대 개수 제한


class TierManager:
    """티어 승격/강등 및 강도 관리"""

    TIER_ORDER = ['ephemeral', 'short_term', 'long_term', 'core']

    TIER_CONFIG: Dict[str, TierConfig] = {
        'ephemeral': TierConfig(
            decay_rate_per_day=0.7,  # 하루에 30% 감쇠
            promotion_threshold_strength=0.3,
            promotion_threshold_reinforcement=None,
            demotion_threshold=0.05,
            max_count=None
        ),
        'short_term': TierConfig(
            decay_rate_per_day=0.9,  # 하루에 10% 감쇠
            promotion_threshold_strength=None,
            promotion_threshold_reinforcement=3,
            demotion_threshold=0.1,
            max_count=100
        ),
        'long_term': TierConfig(
            decay_rate_per_day=0.98,  # 하루에 2% 감쇠
            promotion_threshold_strength=None,
            promotion_threshold_reinforcement=10,
            demotion_threshold=0.2,
            max_count=50
        ),
        'core': TierConfig(
            decay_rate_per_day=1.0,  # 감쇠 없음
            promotion_threshold_strength=None,
            promotion_threshold_reinforcement=None,
            demotion_threshold=0.0,  # 강등 없음
            max_count=20
        )
    }

    def calculate_current_strength(self, insp: Inspiration) -> float:
        """현재 시점의 실제 강도 계산 (감쇠 적용)"""
        config = self.TIER_CONFIG[insp.tier]

        # 시간 경과 계산
        if insp.last_reinforced_at:
            hours_since = (datetime.now() - insp.last_reinforced_at).total_seconds() / 3600
        else:
            hours_since = (datetime.now() - insp.created_at).total_seconds() / 3600

        days_since = hours_since / 24

        # 기본 감쇠
        base_decay = config.decay_rate_per_day ** days_since

        # 감정적 임팩트가 높으면 감쇠 느림 (최대 30% 감소)
        emotional_factor = 1 - (insp.emotional_impact * 0.3)
        adjusted_decay = base_decay ** emotional_factor

        # 강화 횟수 많으면 감쇠 느림
        reinforcement_factor = 1 / (1 + insp.reinforcement_count * 0.1)
        adjusted_decay = adjusted_decay ** reinforcement_factor

        return insp.strength * adjusted_decay

    def check_promotion(self, insp: Inspiration) -> Tuple[bool, Optional[str]]:
        """승격 가능 여부 확인

        Returns:
            (승격 여부, 새 티어 또는 None)
        """
        current_idx = self.TIER_ORDER.index(insp.tier)

        # 이미 최고 티어
        if current_idx >= len(self.TIER_ORDER) - 1:
            return False, None

        config = self.TIER_CONFIG[insp.tier]
        next_tier = self.TIER_ORDER[current_idx + 1]

        # 강도 기반 승격 (ephemeral → short_term)
        if config.promotion_threshold_strength is not None:
            if insp.strength >= config.promotion_threshold_strength:
                return True, next_tier

        # 강화 횟수 기반 승격 (short_term → long_term, long_term → core)
        if config.promotion_threshold_reinforcement is not None:
            if insp.reinforcement_count >= config.promotion_threshold_reinforcement:
                return True, next_tier

        return False, None

    def check_demotion(self, insp: Inspiration, current_strength: float) -> Tuple[str, Optional[str]]:
        """강등 또는 삭제 여부 확인

        Returns:
            ('keep' | 'demote' | 'delete', 새 티어 또는 None)
        """
        config = self.TIER_CONFIG[insp.tier]

        if current_strength < config.demotion_threshold:
            if insp.tier == 'ephemeral':
                return 'delete', None
            else:
                # 한 단계 강등
                current_idx = self.TIER_ORDER.index(insp.tier)
                new_tier = self.TIER_ORDER[current_idx - 1]
                return 'demote', new_tier

        return 'keep', None

    def promote(self, insp: Inspiration) -> bool:
        """승격 실행

        Returns:
            승격 여부
        """
        should_promote, new_tier = self.check_promotion(insp)

        if should_promote and new_tier:
            insp.tier = new_tier
            return True

        return False

    def demote_or_delete(self, insp: Inspiration, current_strength: float) -> str:
        """강등 또는 삭제 실행

        Returns:
            'keep', 'demoted', 'delete' 중 하나
        """
        action, new_tier = self.check_demotion(insp, current_strength)

        if action == 'demote' and new_tier:
            insp.tier = new_tier
            return 'demoted'

        return action

    def get_tier_limits_exceeded(self, tier_counts: Dict[str, int]) -> Dict[str, int]:
        """티어별 초과 개수 반환"""
        exceeded = {}

        for tier, count in tier_counts.items():
            config = self.TIER_CONFIG.get(tier)
            if config and config.max_count and count > config.max_count:
                exceeded[tier] = count - config.max_count

        return exceeded

    def create_core_memory_from_inspiration(self, insp: Inspiration) -> CoreMemory:
        """영감을 Core Memory로 변환"""
        # 유형 판단
        core_type = self._classify_core_type(insp)

        # 페르소나 영향 정의
        if core_type == 'obsession':
            persona_impact = f"'{insp.topic}'에 대해 자주 언급하고 관심을 보입니다."
        elif core_type == 'opinion':
            persona_impact = f"'{insp.topic}'에 대해 확고한 의견을 가지고 있습니다."
        elif core_type == 'theme':
            persona_impact = f"대화와 글에서 '{insp.topic}' 테마가 자주 등장합니다."
        else:
            persona_impact = f"'{insp.topic}'이 기억에 남아 있습니다."

        return CoreMemory(
            id=generate_id(),
            type=core_type,
            content=insp.my_angle or insp.topic,
            formed_from_inspiration_id=insp.id,
            total_reinforcements=insp.reinforcement_count,
            persona_impact=persona_impact,
            created_at=datetime.now()
        )

    def _classify_core_type(self, insp: Inspiration) -> str:
        """영감의 Core 유형 판단"""
        # 강화 횟수가 매우 높으면 obsession
        if insp.reinforcement_count >= 15:
            return 'obsession'

        # 여러 번 글로 썼으면 theme
        if insp.used_count >= 3:
            return 'theme'

        # my_angle에 의견이 있으면 opinion
        if insp.my_angle and any(word in insp.my_angle for word in ['생각', '의견', '믿', '확신']):
            return 'opinion'

        # 기본값
        return 'theme'

    def get_core_context_for_llm(self, core_memories: list) -> str:
        """LLM 프롬프트에 주입할 Core 기억 컨텍스트"""
        if not core_memories:
            return ""

        context = "### 🧠 CORE MEMORIES (장기 기억):\n"

        obsessions = [c for c in core_memories if c.type == 'obsession']
        if obsessions:
            context += "**집착하는 주제**: " + ", ".join([c.content for c in obsessions]) + "\n"

        opinions = [c for c in core_memories if c.type == 'opinion']
        if opinions:
            context += "**확고한 의견**: " + ", ".join([c.content for c in opinions]) + "\n"

        themes = [c for c in core_memories if c.type == 'theme']
        if themes:
            context += "**반복 테마**: " + ", ".join([c.content for c in themes]) + "\n"

        return context


# Global instance
tier_manager = TierManager()
