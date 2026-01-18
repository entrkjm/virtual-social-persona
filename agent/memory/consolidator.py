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
    accelerated_decay_applied: int
    over_soft_ceiling: bool
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
        """정리 실행 (주기적으로 호출) - 품질 경쟁 기반

        Returns:
            정리 결과 통계
        """
        start_time = datetime.now()

        stats = {
            'deleted': 0,
            'demoted': 0,
            'promoted': 0,
            'accelerated_decay_applied': 0
        }

        all_inspirations = self.db.get_all_inspirations()
        total_count = len(all_inspirations)

        over_soft_ceiling = self.tier_manager.is_over_soft_ceiling(total_count)
        if over_soft_ceiling:
            print(f"[CONSOLIDATION] Over soft ceiling: {total_count}/{self.tier_manager.CAPACITY_CONFIG.soft_ceiling}")

        # 1. 강도 계산 및 정렬 (품질 경쟁)
        strength_map = []
        for insp in all_inspirations:
            current_strength = self.tier_manager.calculate_current_strength(insp)
            strength_map.append((insp, current_strength))

        strength_map.sort(key=lambda x: x[1])

        # 2. 하위 N% 식별
        bottom_count = self.tier_manager.get_bottom_percentile_count(total_count)
        bottom_inspirations = set(insp.id for insp, _ in strength_map[:bottom_count])

        # 3. 모든 영감 처리
        for insp, current_strength in strength_map:
            is_bottom = insp.id in bottom_inspirations

            # 하위 N%는 가속 감쇠 적용
            if is_bottom and insp.tier != 'core':
                config = self.tier_manager.TIER_CONFIG[insp.tier]
                accelerated_decay = self.tier_manager.get_accelerated_decay_rate(config.decay_rate_per_day)
                current_strength *= accelerated_decay
                stats['accelerated_decay_applied'] += 1

            insp.strength = current_strength

            # 최소 생존 강도 이하면 삭제
            if current_strength < self.tier_manager.CAPACITY_CONFIG.min_strength_to_survive:
                self.db.delete_inspiration(insp.id)
                if self.vector_store:
                    self.vector_store.delete_inspiration(insp.id)
                stats['deleted'] += 1
                continue

            # 강등 체크
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
                if insp.tier == 'core':
                    core_memory = self.tier_manager.create_core_memory_from_inspiration(insp)
                    self.db.add_core_memory(core_memory)

            self.db.update_inspiration(insp)
            self._sync_vector_metadata(insp)

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        self.last_run = end_time

        result = ConsolidationStats(
            deleted=stats['deleted'],
            demoted=stats['demoted'],
            promoted=stats['promoted'],
            accelerated_decay_applied=stats['accelerated_decay_applied'],
            over_soft_ceiling=over_soft_ceiling,
            duration_ms=duration_ms
        )

        self._log_stats(result)
        return result

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
        print(f"  - Accelerated decay: {stats.accelerated_decay_applied}")
        if stats.over_soft_ceiling:
            print(f"  - WARNING: Over soft ceiling!")

    def should_run(self, interval_hours: int = 1) -> bool:
        """실행 필요 여부 확인"""
        if self.last_run is None:
            return True

        hours_since = (datetime.now() - self.last_run).total_seconds() / 3600
        return hours_since >= interval_hours

    def get_memory_health(self) -> Dict:
        """메모리 상태 리포트 (품질 경쟁 기반)"""
        tier_counts = self.db.count_inspirations_by_tier()
        core_memories = self.db.get_all_core_memories()

        vector_count = 0
        if self.vector_store:
            vector_stats = self.vector_store.get_stats()
            vector_count = vector_stats['inspirations_count']

        total = sum(tier_counts.values())
        capacity_config = self.tier_manager.CAPACITY_CONFIG

        return {
            'tier_counts': tier_counts,
            'total_inspirations': total,
            'soft_ceiling': capacity_config.soft_ceiling,
            'ceiling_usage': f"{total / capacity_config.soft_ceiling * 100:.1f}%",
            'over_ceiling': total > capacity_config.soft_ceiling,
            'vector_count': vector_count,
            'core_memories': len(core_memories),
            'last_consolidation': self.last_run.isoformat() if self.last_run else None
        }


# Global instance
memory_consolidator = MemoryConsolidator()
