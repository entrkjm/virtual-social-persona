"""
Base Scenario
시나리오의 공통 인터페이스 정의
"""
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from datetime import datetime

from agent.memory.database import MemoryDatabase, PersonMemory, ConversationRecord, generate_id


@dataclass
class ScenarioContext:
    """시나리오 실행 컨텍스트"""
    person: Optional[PersonMemory]
    post_id: Optional[str]
    post_text: Optional[str]
    conversation: Optional[ConversationRecord]
    extra: Dict[str, Any]


@dataclass
class ScenarioResult:
    """시나리오 실행 결과"""
    success: bool
    action: Optional[str] = None  # 'like', 'reply', 'repost', 'follow', 'skip'
    content: Optional[str] = None  # 생성된 답글 등
    details: Optional[Dict[str, Any]] = None


class BaseScenario(ABC):
    """시나리오 베이스 클래스"""

    def __init__(self, memory_db: MemoryDatabase, platform: str = 'twitter'):
        self.memory_db = memory_db
        self.platform = platform

    @abstractmethod
    def execute(self, data: Dict[str, Any]) -> Optional[ScenarioResult]:
        """시나리오 실행 (템플릿 메서드)"""
        pass

    def get_person(self, user_id: str, screen_name: str) -> PersonMemory:
        """PersonMemory 조회 또는 생성"""
        return self.memory_db.get_or_create_person(user_id, screen_name, self.platform)

    def get_or_create_conversation(
        self,
        person_id: str,
        post_id: str,
        conversation_type: str
    ) -> ConversationRecord:
        """대화 기록 조회 또는 생성"""
        # 기존 대화 찾기
        conversations = self.memory_db.get_conversations_by_person(person_id, self.platform, limit=5)
        for conv in conversations:
            if conv.post_id == post_id and conv.state == 'ongoing':
                return conv

        # 새 대화 생성
        now = datetime.now()
        conv = ConversationRecord(
            id=generate_id(),
            person_id=person_id,
            platform=self.platform,
            post_id=post_id,
            conversation_type=conversation_type,
            topic=None,
            summary="",
            turn_count=0,
            state='ongoing',
            started_at=now,
            last_updated_at=now
        )
        self.memory_db.add_conversation(conv)
        return conv

    def update_person_after_interaction(
        self,
        person: PersonMemory,
        interaction_type: str,
        summary: Optional[str] = None
    ):
        """상호작용 후 PersonMemory 업데이트"""
        person.last_interaction_at = datetime.now()

        # Tier 자동 승격 로직 (단순화)
        if person.tier == 'stranger':
            person.tier = 'acquaintance'
        elif person.tier == 'acquaintance':
            # acquaintance → familiar: 상호작용 3회 이상
            convs = self.memory_db.get_conversations_by_person(person.user_id, self.platform)
            if len(convs) >= 3:
                person.tier = 'familiar'

        # Affinity 조정 (기본 +0.05)
        person.affinity = min(1.0, person.affinity + 0.05)

        self.memory_db.update_person(person)

    def update_conversation_after_turn(
        self,
        conv: ConversationRecord,
        summary: str,
        is_concluded: bool = False
    ):
        """대화 턴 후 업데이트"""
        conv.turn_count += 1
        conv.summary = summary
        conv.last_updated_at = datetime.now()

        if is_concluded:
            conv.state = 'concluded'

        self.memory_db.update_conversation(conv)

    def get_recent_replies(self, limit: int = 5) -> List[str]:
        """최근 답글 내용 조회 (말투 반복 방지용)"""
        episodes = self.memory_db.get_recent_episodes(limit=limit * 2, type_filter='replied')
        return [e.content for e in episodes if e.content][:limit]
