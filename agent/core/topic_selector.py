"""
Topic Selector
가중치 기반 토픽 선택 + 쿨다운 추적
Weighted topic selection with cooldown tracking
"""
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from agent.persona.persona_loader import active_persona


@dataclass
class TopicSource:
    name: str
    weight: float
    keywords: List[str] = field(default_factory=list)


class TopicSelector:
    """가중치 기반 토픽 선택기"""

    # 소스별 가중치
    SOURCE_WEIGHTS = {
        'core': 1.0,        # 페르소나 본질
        'time': 1.2,        # 시간대별
        'curiosity': 2.0,   # 최근 관심사
        'inspiration': 2.5, # flash/brewing 영감
        'trends': 1.5,      # 트위터 트렌드
    }

    COOLDOWN_STEPS = 3  # 최근 N스텝 사용한 키워드 제외

    def __init__(self):
        self._recent_queries: deque = deque(maxlen=self.COOLDOWN_STEPS)
        self._last_selection: Optional[Tuple[str, str]] = None  # (keyword, source)

    def select(
        self,
        core_keywords: List[str],
        time_keywords: List[str],
        curiosity_keywords: List[str],
        trend_keywords: List[str],
        inspiration_topics: List[str] = None
    ) -> Tuple[str, str]:
        """토픽 선택

        Returns:
            (keyword, source_name) 튜플
        """
        inspiration_topics = inspiration_topics or []

        sources = [
            TopicSource('core', self.SOURCE_WEIGHTS['core'], core_keywords),
            TopicSource('time', self.SOURCE_WEIGHTS['time'], time_keywords),
            TopicSource('curiosity', self.SOURCE_WEIGHTS['curiosity'], curiosity_keywords),
            TopicSource('inspiration', self.SOURCE_WEIGHTS['inspiration'], inspiration_topics),
            TopicSource('trends', self.SOURCE_WEIGHTS['trends'], trend_keywords),
        ]

        # 쿨다운 적용: 최근 사용한 키워드 제외
        cooled_sources = self._apply_cooldown(sources)

        # 빈 소스 제외
        valid_sources = [s for s in cooled_sources if s.keywords]

        if not valid_sources:
            # 쿨다운으로 다 막혔으면 core에서 랜덤
            domain_fallback = active_persona.domain.fallback_topics[0] if active_persona.domain and active_persona.domain.fallback_topics else "topic"
            fallback = random.choice(core_keywords) if core_keywords else domain_fallback
            return fallback, 'core_fallback'

        # 가중치 기반 선택
        keyword, source_name = self._weighted_select(valid_sources)

        # 쿨다운 기록
        self._recent_queries.append(keyword)
        self._last_selection = (keyword, source_name)

        return keyword, source_name

    def _apply_cooldown(self, sources: List[TopicSource]) -> List[TopicSource]:
        """쿨다운 적용 - 최근 사용한 키워드 제외"""
        recent_set = set(self._recent_queries)

        result = []
        for source in sources:
            filtered = [kw for kw in source.keywords if kw not in recent_set]
            result.append(TopicSource(source.name, source.weight, filtered))

        return result

    def _weighted_select(self, sources: List[TopicSource]) -> Tuple[str, str]:
        """가중치 기반 선택"""
        # (keyword, source_name, weight) 리스트 구성
        candidates = []
        for source in sources:
            for kw in source.keywords:
                candidates.append((kw, source.name, source.weight))

        if not candidates:
            domain_fallback = active_persona.domain.fallback_topics[0] if active_persona.domain and active_persona.domain.fallback_topics else "topic"
            return domain_fallback, "fallback"

        # 가중치 기반 랜덤 선택
        weights = [c[2] for c in candidates]
        selected = random.choices(candidates, weights=weights, k=1)[0]

        return selected[0], selected[1]

    def get_last_selection(self) -> Optional[Tuple[str, str]]:
        return self._last_selection

    def get_recent_queries(self) -> List[str]:
        return list(self._recent_queries)

    def reset_cooldown(self):
        """쿨다운 리셋 (테스트용)"""
        self._recent_queries.clear()


# Global instance
topic_selector = TopicSelector()
