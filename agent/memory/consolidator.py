"""
Memory Consolidator
주기적 메모리 정리 및 최적화
Periodic memory cleanup and optimization
"""
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

from agent.memory.database import MemoryDatabase
from agent.memory.tier_manager import TierManager

try:
    from agent.memory.vector_store import VectorStore
except ImportError:
    VectorStore = None


@dataclass
class ConsolidationStats:
    """정리 결과 통계"""
    deleted: int
    demoted: int
    promoted: int
    tier_enforced: int
    duration_ms: int


class MemoryConsolidator:
    """메모리 정리 및 최적화"""

    def __init__(
        self,
        db: Optional[MemoryDatabase] = None,
        vector_store: Optional[VectorStore] = None,
        tier_manager: Optional[TierManager] = None
    ):
        from agent.memory.database import memory_db
        from agent.memory.tier_manager import tier_manager as tm

        try:
            from agent.memory.vector_store import vector_store as vs
        except ImportError:
            vs = None

        self.db = db or memory_db
        self.vector_store = vector_store or vs
        self.tier_manager = tier_manager or tm

        self.last_run: Optional[datetime] = None

    def run(self) -> ConsolidationStats:
        """정리 실행 (주기적으로 호출)

        Returns:
            정리 결과 통계
        """
        start_time = datetime.now()

        stats = {
            'deleted': 0,
            'demoted': 0,
            'promoted': 0,
            'tier_enforced': 0
        }

        # 1. 모든 영감 순회하며 강도 업데이트 + 승격/강등
        all_inspirations = self.db.get_all_inspirations()

        for insp in all_inspirations:
            # 현재 강도 계산
            current_strength = self.tier_manager.calculate_current_strength(insp)
            insp.strength = current_strength

            # 강등/삭제 체크
            action = self.tier_manager.demote_or_delete(insp, current_strength)

            if action == 'delete':
                self.db.delete_inspiration(insp.id)
                if self.vector_store:
                    self.vector_store.delete_inspiration(insp.id)
                stats['deleted'] += 1
                continue

            if action == 'demoted':
                stats['demoted'] += 1

            # 승격 체크
            if self.tier_manager.promote(insp):
                stats['promoted'] += 1

                # Core로 승격 시 페르소나 통합
                if insp.tier == 'core':
                    core_memory = self.tier_manager.create_core_memory_from_inspiration(insp)
                    self.db.add_core_memory(core_memory)

            # 변경사항 저장
            self.db.update_inspiration(insp)
            self._sync_vector_metadata(insp)

        # 2. 티어별 개수 제한 적용
        tier_enforced = self._enforce_tier_limits()
        stats['tier_enforced'] = tier_enforced

        # 완료
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        self.last_run = end_time

        result = ConsolidationStats(
            deleted=stats['deleted'],
            demoted=stats['demoted'],
            promoted=stats['promoted'],
            tier_enforced=stats['tier_enforced'],
            duration_ms=duration_ms
        )

        self._log_stats(result)
        return result

    def _enforce_tier_limits(self) -> int:
        """티어별 최대 개수 초과 시 약한 것부터 강등"""
        tier_counts = self.db.count_inspirations_by_tier()
        exceeded = self.tier_manager.get_tier_limits_exceeded(tier_counts)

        total_enforced = 0

        for tier, excess_count in exceeded.items():
            # 해당 티어에서 강도 낮은 순으로 가져오기
            weak_inspirations = self.db.get_inspirations_by_tier(
                tier,
                order_by="strength ASC",
                limit=excess_count
            )

            for insp in weak_inspirations:
                current_strength = self.tier_manager.calculate_current_strength(insp)
                action = self.tier_manager.demote_or_delete(insp, current_strength)

                if action == 'delete':
                    self.db.delete_inspiration(insp.id)
                    if self.vector_store:
                        self.vector_store.delete_inspiration(insp.id)
                elif action in ['demoted', 'keep']:
                    # 강제 강등
                    tier_order = self.tier_manager.TIER_ORDER
                    current_idx = tier_order.index(insp.tier)
                    if current_idx > 0:
                        insp.tier = tier_order[current_idx - 1]
                        self.db.update_inspiration(insp)
                        self._sync_vector_metadata(insp)

                total_enforced += 1

        return total_enforced

    def _sync_vector_metadata(self, insp):
        """Vector Store 메타데이터 동기화"""
        if not self.vector_store:
            return

        self.vector_store.update_inspiration_metadata(
            id=insp.id,
            metadata={
                'tier': insp.tier,
                'strength': insp.strength,
                'topic': insp.topic,
                'emotional_impact': insp.emotional_impact,
                'reinforcement_count': insp.reinforcement_count
            }
        )

    def _log_stats(self, stats: ConsolidationStats):
        """통계 로깅"""
        print(f"[CONSOLIDATION] Completed in {stats.duration_ms}ms")
        print(f"  - Deleted: {stats.deleted}")
        print(f"  - Demoted: {stats.demoted}")
        print(f"  - Promoted: {stats.promoted}")
        print(f"  - Tier enforced: {stats.tier_enforced}")

    def should_run(self, interval_hours: int = 1) -> bool:
        """실행 필요 여부 확인"""
        if self.last_run is None:
            return True

        hours_since = (datetime.now() - self.last_run).total_seconds() / 3600
        return hours_since >= interval_hours

    def get_memory_health(self) -> Dict:
        """메모리 상태 리포트"""
        tier_counts = self.db.count_inspirations_by_tier()
        core_memories = self.db.get_all_core_memories()

        vector_count = 0
        if self.vector_store:
            vector_stats = self.vector_store.get_stats()
            vector_count = vector_stats['inspirations_count']

        # 티어별 한계 대비 비율
        tier_health = {}
        for tier, config in self.tier_manager.TIER_CONFIG.items():
            count = tier_counts.get(tier, 0)
            max_count = config.max_count
            if max_count:
                tier_health[tier] = {
                    'count': count,
                    'max': max_count,
                    'usage': f"{count / max_count * 100:.1f}%"
                }
            else:
                tier_health[tier] = {
                    'count': count,
                    'max': 'unlimited',
                    'usage': 'N/A'
                }

        return {
            'tier_health': tier_health,
            'total_inspirations': sum(tier_counts.values()),
            'vector_count': vector_count,
            'core_memories': len(core_memories),
            'last_consolidation': self.last_run.isoformat() if self.last_run else None
        }


# Global instance
memory_consolidator = MemoryConsolidator()
