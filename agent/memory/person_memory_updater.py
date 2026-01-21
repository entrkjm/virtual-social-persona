"""
Person Memory Updater
LLM 기반 who_is_this 자동 업데이트
Auto-update who_is_this field using LLM summarization
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from agent.memory.database import PersonMemory, MemoryDatabase
from core.llm import llm_client


class PersonMemoryUpdater:
    """
    LLM 기반 PersonMemory.who_is_this 업데이트

    상호작용 기록을 바탕으로 "이 사람은 누구인가" 요약 생성
    """

    MIN_INTERACTIONS_FOR_UPDATE = 3
    MAX_CONVERSATIONS_FOR_PROMPT = 5
    MAX_MOMENTS_FOR_PROMPT = 3

    SYSTEM_PROMPT = """당신은 소셜 미디어 사용자입니다.
상대방과의 대화 기록을 보고 "이 사람은 누구인가"를 한 문장으로 요약하세요.

요약 기준:
1. 관계 수준 (얼마나 친한지)
2. 공통 관심사 또는 대화 주제
3. 인상적인 특징 (있다면)

규칙:
- 한 문장 (50자 이내)
- 자연스러운 메모처럼 작성
- 예: "요리에 관심 많은 개발자, 자주 대화하는 사이"
- 예: "가끔 음식 사진에 반응하는 트친"
- 예: "한식 관련 질문 자주 하는 분"

정보가 부족하면 "아직 잘 모르는 사람" 정도로 짧게 작성하세요."""

    def __init__(self, db: Optional[MemoryDatabase] = None):
        self.db = db

    def should_update(self, person: PersonMemory) -> bool:
        """업데이트 필요 여부 확인"""
        has_enough_data = (
            len(person.latest_conversations) >= self.MIN_INTERACTIONS_FOR_UPDATE
            or len(person.memorable_moments) >= 1
        )
        return has_enough_data

    def update_who_is_this(self, person: PersonMemory, force: bool = False) -> Optional[str]:
        """
        who_is_this 필드를 LLM으로 업데이트

        Args:
            person: 업데이트할 PersonMemory
            force: True면 데이터 충분성 검사 건너뜀

        Returns:
            생성된 요약 문자열 (실패 시 None)
        """
        if not force and not self.should_update(person):
            return None

        prompt = self._build_prompt(person)

        try:
            response = llm_client.generate(prompt, system_prompt=self.SYSTEM_PROMPT)
            summary = self._clean_response(response)

            person.who_is_this = summary
            person.updated_at = datetime.now()

            if self.db:
                self.db.update_person(person)

            return summary
        except Exception as e:
            print(f"[PersonMemoryUpdater] LLM failed: {e}")
            return None

    def _build_prompt(self, person: PersonMemory) -> str:
        """프롬프트 생성"""
        parts = [f"상대방: @{person.screen_name}"]
        parts.append(f"관계 수준: {person.tier}")
        parts.append(f"친밀도: {person.affinity:.2f}")

        if person.memorable_moments:
            parts.append("\n기억에 남는 순간:")
            for moment in person.memorable_moments[:self.MAX_MOMENTS_FOR_PROMPT]:
                date = moment.get('date', '')
                summary = moment.get('summary', '')
                parts.append(f"- [{date}] {summary}")

        if person.latest_conversations:
            parts.append("\n최근 대화:")
            for conv in person.latest_conversations[:self.MAX_CONVERSATIONS_FOR_PROMPT]:
                topic = conv.get('topic', '일반')
                summary = conv.get('summary', '')
                parts.append(f"- [{topic}] {summary}")

        if person.who_is_this:
            parts.append(f"\n기존 메모: {person.who_is_this}")

        parts.append("\n이 사람을 한 문장으로 요약해주세요.")
        return "\n".join(parts)

    def _clean_response(self, response: str) -> str:
        """LLM 응답 정제"""
        cleaned = response.strip()
        cleaned = cleaned.strip('"\'')

        if len(cleaned) > 100:
            cleaned = cleaned[:100]

        return cleaned

    def batch_update(
        self,
        persons: List[PersonMemory],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        여러 PersonMemory 일괄 업데이트

        Args:
            persons: 업데이트할 PersonMemory 목록
            force: True면 조건 무시하고 강제 업데이트

        Returns:
            통계 정보
        """
        stats = {
            'total': len(persons),
            'updated': 0,
            'skipped': 0,
            'failed': 0
        }

        for person in persons:
            if not force and not self.should_update(person):
                stats['skipped'] += 1
                continue

            result = self.update_who_is_this(person, force=force)
            if result:
                stats['updated'] += 1
            else:
                stats['failed'] += 1

        return stats
