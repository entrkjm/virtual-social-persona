"""
Reply Generator
LLM 기반 답글 생성

EngagementJudge가 reply로 결정한 후 호출
"""
import logging
from typing import Dict, Any, Optional, List, Set

from core.llm import llm_client
from agent.memory.database import PersonMemory

logger = logging.getLogger("agent")

# 유사도 체크용 상수
SIMILARITY_THRESHOLD = 0.5  # 50% 이상 겹치면 재생성
MAX_REGENERATION_ATTEMPTS = 3


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
        context: Optional[Dict[str, Any]] = None,
        recent_replies: Optional[List[str]] = None
    ) -> str:
        """
        답글 생성

        Args:
            post_text: 원본 포스트 텍스트
            person: 상대방 PersonMemory
            reply_type: 'short', 'normal', 'long'
            context: 추가 컨텍스트
            recent_replies: 최근 답글 5개 (말투 반복 방지용)
        """
        logger.debug(f"[ReplyGen] Generating: type={reply_type}, person={person.screen_name if person else 'N/A'}")

        for attempt in range(MAX_REGENERATION_ATTEMPTS):
            prompt = self._build_prompt(post_text, person, reply_type, context, recent_replies)

            try:
                logger.debug(f"[ReplyGen] Calling LLM (attempt {attempt + 1})...")
                response = llm_client.generate(prompt, system_prompt=self.system_prompt)
                cleaned = self._clean_response(response)

                # 유사도 체크
                if recent_replies:
                    similarity, similar_to = self._check_similarity(cleaned, recent_replies)
                    if similarity >= SIMILARITY_THRESHOLD:
                        logger.warning(f"[ReplyGen] Too similar ({similarity:.0%}) to: '{similar_to[:30]}...' - regenerating")
                        continue
                    else:
                        logger.info(f"[ReplyGen] Similarity check passed ({similarity:.0%})")
                else:
                    logger.info("[ReplyGen] Similarity check skipped (no recent_replies)")

                logger.info(f"[ReplyGen] Generated ({len(cleaned)} chars): {cleaned[:50]}...")
                return cleaned
            except Exception as e:
                logger.error(f"[ReplyGen] LLM failed: {e}")
                return ""

        logger.warning(f"[ReplyGen] Max regeneration attempts reached, using last result")
        return cleaned if 'cleaned' in locals() else ""

    def _check_similarity(self, new_reply: str, recent_replies: List[str]) -> tuple[float, str]:
        """
        새 답글과 최근 답글들의 유사도 체크 (단어 기반)

        Returns:
            (유사도, 가장 유사한 답글)
        """
        new_words = self._extract_words(new_reply)
        if not new_words:
            return 0.0, ""

        max_similarity = 0.0
        most_similar = ""

        for recent in recent_replies:
            recent_words = self._extract_words(recent)
            if not recent_words:
                continue

            common = new_words & recent_words
            similarity = len(common) / max(len(new_words), len(recent_words))

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar = recent

        return max_similarity, most_similar

    def _extract_words(self, text: str) -> Set[str]:
        """텍스트에서 의미있는 단어 추출 (2자 이상)"""
        import re
        words = re.findall(r'[\w가-힣]+', text.lower())
        return {w for w in words if len(w) >= 2}

    def _build_prompt(
        self,
        post_text: str,
        person: Optional[PersonMemory],
        reply_type: str,
        context: Optional[Dict[str, Any]],
        recent_replies: Optional[List[str]] = None
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

        if recent_replies:
            parts.append("\n[최근 내 답글 - 이와 다른 말투/어미로 작성]")
            for i, reply in enumerate(recent_replies[:5], 1):
                parts.append(f"{i}. {reply}")
            parts.append("위 답글들과 다른 시작 표현, 다른 어미를 사용하세요.")

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
