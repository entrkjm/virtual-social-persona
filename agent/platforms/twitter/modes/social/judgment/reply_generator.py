"""
Reply Generator
LLM 기반 답글 생성

EngagementJudge가 reply로 결정한 후 호출
"""
from typing import Dict, Any, Optional

from core.llm import llm_client
from agent.memory.database import PersonMemory


class ReplyGenerator:
    """
    LLM 기반 답글 생성

    기존 SocialReplyGenerator와 유사하지만 더 단순화
    TODO: persona config 연동하여 말투 적용
    """

    def __init__(self, persona_config: Optional[Dict] = None):
        self.persona_config = persona_config or {}
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 생성"""
        identity = self.persona_config.get('identity', {})
        name = identity.get('name', '사용자')
        personality = identity.get('personality', {})

        speech = self.persona_config.get('speech_style', {})
        chat_style = speech.get('chat', {})
        tone = chat_style.get('tone', '친근하고 자연스러운')

        return f"""당신은 {name}입니다.
성격: {personality.get('brief', '친근한 사람')}
말투: {tone}

답글 작성 규칙:
- 자연스럽고 대화체로
- 너무 길지 않게 (50-100자 권장)
- 이모지 최소화
- 설명 없이 답글 내용만 출력"""

    def generate(
        self,
        post_text: str,
        person: Optional[PersonMemory] = None,
        reply_type: str = 'normal',
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        답글 생성

        Args:
            post_text: 원본 포스트 텍스트
            person: 상대방 PersonMemory
            reply_type: 'short', 'normal', 'long'
            context: 추가 컨텍스트
        """
        prompt = self._build_prompt(post_text, person, reply_type, context)

        try:
            response = llm_client.generate(prompt, system_prompt=self.system_prompt)
            return self._clean_response(response)
        except Exception as e:
            print(f"[ReplyGenerator] LLM failed: {e}")
            return ""

    def _build_prompt(
        self,
        post_text: str,
        person: Optional[PersonMemory],
        reply_type: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """프롬프트 생성"""
        length_guide = {
            'short': '15-50자로 짧게',
            'normal': '50-100자로',
            'long': '100-150자로 자세하게'
        }.get(reply_type, '50-100자로')

        parts = [f"상대방 글: \"{post_text}\""]

        if person:
            parts.append(f"\n상대방: @{person.screen_name}")
            if person.tier in ('familiar', 'friend'):
                parts.append(f"(아는 사람 - {person.tier})")
            if person.who_is_this:
                parts.append(f"메모: {person.who_is_this}")

        if context:
            if context.get('is_reply_to_me'):
                parts.append("\n이 글은 내 글에 대한 답글입니다.")
            if context.get('topic'):
                parts.append(f"주제: {context.get('topic')}")

        parts.append(f"\n{length_guide} 답글을 작성하세요.")
        return "\n".join(parts)

    def _clean_response(self, response: str) -> str:
        """LLM 응답 정리"""
        response = response.strip()

        # 따옴표 제거
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        if response.startswith("'") and response.endswith("'"):
            response = response[1:-1]

        # 너무 길면 자르기
        if len(response) > 200:
            response = response[:200]

        return response
