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

    # 소스별 가중치 (inspiration 낮춤 - 무관 토픽 방지)
    SOURCE_WEIGHTS = {
        'core': 1.0,        # 페르소나 본질
        'time': 1.2,        # 시간대별
        'curiosity': 1.8,   # 최근 관심사
        'inspiration': 1.0, # flash/brewing 영감 (2.5 → 1.0으로 낮춤)
        'trends': 1.5,      # 트위터 트렌드
    }

    COOLDOWN_STEPS = 6  # 최근 N스텝 사용한 키워드 제외 (3 → 6으로 증가)

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

        # 쿼리 확장
        enhanced_query = self._create_combinatorial_query(keyword)

        return enhanced_query, source_name

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

    def _create_combinatorial_query(self, keyword: str) -> str:
        """단순 키워드를 복합 쿼리로 변환 (스팸 필터링)"""
        # 1. Context Keywords 제거 (검색 결과 너무 제한적)
        # context_keywords = ["맛있다", "레시피", "만들기", "추천", "존맛", "요리", "먹고싶다", "맛집"]
        
        # 2. 부정 키워드 (제외)
        negative_keywords = ["crypto", "nft", "giveaway", "bot", "promotion", "광고", "이벤트"]
        negative_query = " ".join([f"-{nw}" for nw in negative_keywords])
        
        # 3. 필터 (링크 필터는 유지하되, 필요시 완화 가능)
        filters = "-filter:links -filter:replies"
        
        # 4. 최종 조합: 키워드 + 부정어 + 필터
        query = f'{keyword} {negative_query} {filters}'
        
        return query

    def get_last_selection(self) -> Optional[Tuple[str, str]]:
        return self._last_selection

    def get_recent_queries(self) -> List[str]:
        return list(self._recent_queries)

    def reset_cooldown(self):
        """쿨다운 리셋 (테스트용)"""
        self._recent_queries.clear()


# Global instance
topic_selector = TopicSelector()
