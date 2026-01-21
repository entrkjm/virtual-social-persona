"""
Engagement Judge
LLM 기반 engagement 판단 (like/reply/skip)

시나리오에서 호출하여 실제 판단 수행
"""
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

from core.llm import llm_client
from agent.memory.database import PersonMemory


@dataclass
class JudgmentResult:
    """판단 결과"""
    action: str  # 'like', 'reply', 'repost', 'skip'
    confidence: float  # 0.0 ~ 1.0
    reason: str
    reply_type: Optional[str] = None  # 'short', 'normal', 'long'


class EngagementJudge:
    """
    LLM 기반 engagement 판단

    입력: 포스트 정보 + PersonMemory + 상황 컨텍스트
    출력: 어떤 액션을 취할지 결정
    """

    SYSTEM_PROMPT = """당신은 소셜 미디어 사용자입니다.
주어진 포스트와 상황을 보고 어떻게 반응할지 결정하세요.

판단 기준:
1. 관계: 아는 사람이면 더 적극적으로 반응
2. 내용: 질문이면 답변, 공감가면 좋아요
3. 컨텍스트: 내 글에 대한 반응이면 더 신경 써서 대응

반드시 아래 JSON 형식으로만 응답하세요:
{"action": "like|reply|skip", "confidence": 0.0-1.0, "reason": "짧은 이유", "reply_type": "short|normal|long 또는 null"}"""

    def judge(
        self,
        post_text: str,
        person: Optional[PersonMemory] = None,
        scenario_type: str = "feed",
        extra_context: Optional[Dict[str, Any]] = None
    ) -> JudgmentResult:
        """
        engagement 판단

        Args:
            post_text: 포스트 텍스트
            person: 상대방 PersonMemory (있으면)
            scenario_type: 시나리오 타입 (notification/feed)
            extra_context: 추가 컨텍스트
        """
        prompt = self._build_prompt(post_text, person, scenario_type, extra_context)

        try:
            response = llm_client.generate(prompt, system_prompt=self.SYSTEM_PROMPT)
            return self._parse_response(response)
        except Exception as e:
            print(f"[EngagementJudge] LLM failed: {e}")
            return JudgmentResult(
                action='skip',
                confidence=0.0,
                reason=f'LLM error: {e}'
            )

    def _build_prompt(
        self,
        post_text: str,
        person: Optional[PersonMemory],
        scenario_type: str,
        extra_context: Optional[Dict[str, Any]]
    ) -> str:
        """프롬프트 생성"""
        parts = [f"포스트: \"{post_text}\""]

        if person:
            parts.append(f"\n상대방 정보:")
            parts.append(f"- 닉네임: @{person.screen_name}")
            parts.append(f"- 관계: {person.tier}")
            if person.who_is_this:
                parts.append(f"- 메모: {person.who_is_this}")

        parts.append(f"\n시나리오: {scenario_type}")

        if extra_context:
            if extra_context.get('is_reply_to_me'):
                parts.append("- 내 글에 대한 답글임")
            if extra_context.get('is_question'):
                parts.append("- 질문 형태임")

        parts.append("\n어떻게 반응할지 JSON으로 응답하세요.")
        return "\n".join(parts)

    def _parse_response(self, response: str) -> JudgmentResult:
        """LLM 응답 파싱"""
        try:
            # JSON 추출 시도
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)

                return JudgmentResult(
                    action=data.get('action', 'skip'),
                    confidence=float(data.get('confidence', 0.5)),
                    reason=data.get('reason', ''),
                    reply_type=data.get('reply_type')
                )
        except json.JSONDecodeError:
            pass

        # 파싱 실패 시 기본값
        if 'reply' in response.lower():
            return JudgmentResult(action='reply', confidence=0.5, reason='parsed from text')
        if 'like' in response.lower():
            return JudgmentResult(action='like', confidence=0.5, reason='parsed from text')

        return JudgmentResult(action='skip', confidence=0.3, reason='parse failed')
