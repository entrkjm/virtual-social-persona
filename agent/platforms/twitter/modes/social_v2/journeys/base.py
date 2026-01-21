"""
Base Journey
Journey의 공통 인터페이스 정의
"""
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
from dataclasses import dataclass

from agent.memory.database import MemoryDatabase, PersonMemory


@dataclass
class JourneyResult:
    """Journey 실행 결과"""
    success: bool
    scenario_executed: Optional[str] = None
    action_taken: Optional[str] = None
    target_user: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class BaseJourney(ABC):
    """Journey 베이스 클래스"""

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter'):
        self.memory_db = memory_db
        self.platform = platform

    @abstractmethod
    def run(self) -> Optional[JourneyResult]:
        """Journey 실행"""
        pass

    def get_person(self, user_id: str, screen_name: str) -> PersonMemory:
        """PersonMemory 조회 또는 생성"""
        return self.memory_db.get_or_create_person(user_id, screen_name, self.platform)
