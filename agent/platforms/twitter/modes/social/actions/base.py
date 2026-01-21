"""
Base Action
액션의 공통 인터페이스 정의
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ActionResult:
    """액션 실행 결과"""
    success: bool
    action_type: str
    target_id: Optional[str] = None
    content: Optional[str] = None
    error: Optional[str] = None


class BaseAction(ABC):
    """액션 베이스 클래스"""

    @abstractmethod
    def execute(self, **kwargs) -> ActionResult:
        """액션 실행"""
        pass

    @abstractmethod
    def can_execute(self, **kwargs) -> bool:
        """실행 가능 여부 확인"""
        pass
