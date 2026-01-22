"""
Engagement Judge
LLM 기반 engagement 판단 (like/reply/repost - 독립적)

시나리오에서 호출하여 실제 판단 수행
"""
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from core.llm import llm_client
from agent.memory.database import PersonMemory

logger = logging.getLogger("agent")


@dataclass
class JudgmentResult:
    """판단 결과 - 각 액션은 독립적"""
    like: bool = False
    repost: bool = False
    reply: bool = False
    reply_type: Optional[str] = None  # 'short', 'normal', 'long'
    confidence: float = 0.5
    reason: str = ""

    @property
    def action(self) -> str:
        """하위 호환: 주요 액션 반환"""
        if self.reply:
            return 'reply'
        if self.repost:
            return 'repost'
        if self.like:
            return 'like'
        return 'skip'

    @property
    def actions(self) -> Dict[str, bool]:
        """독립적 액션 dict"""
        return {'like': self.like, 'repost': self.repost, 'reply': self.reply}


class EngagementJudge:
    """
    LLM 기반 engagement 판단

    입력: 포스트 정보 + PersonMemory + 상황 컨텍스트
    출력: 독립적인 액션 결정 (like, repost, reply 각각 true/false)
    """

    SYSTEM_PROMPT = """당신은 소셜 미디어 사용자입니다.
주어진 포스트와 상황을 보고 어떻게 반응할지 결정하세요.

각 액션은 독립적입니다 (여러 개 동시 선택 가능):
- like: 좋아요 (공감하면)
- repost: 리포스트 (공유하고 싶으면)
- reply: 답글 (할 말이 있으면)

판단 기준:
1. 관계: 아는 사람이면 더 적극적으로 반응
2. 내용: 공감가면 like, 공유할 가치 있으면 repost, 할 말 있으면 reply
3. 컨텍스트: 내 글에 대한 반응이면 더 신경 써서 대응
4. 기존 답글: 이미 비슷한 답글이 달려있으면 reply 안 함

반드시 아래 JSON 형식으로만 응답하세요:
{"like": true/false, "repost": true/false, "reply": true/false, "reply_type": "short|normal|long 또는 null", "reason": "짧은 이유"}"""

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
        logger.debug(f"[Judge] Judging: scenario={scenario_type}, person={person.screen_name if person else 'N/A'}")
        logger.debug(f"[Judge] Post text: {post_text[:80]}...")

        prompt = self._build_prompt(post_text, person, scenario_type, extra_context)

        try:
            logger.debug("[Judge] Calling LLM...")
            response = llm_client.generate(prompt, system_prompt=self.SYSTEM_PROMPT)
            logger.debug(f"[Judge] LLM response: {response[:100]}...")
            result = self._parse_response(response)
            logger.info(f"[Judge] Result: like={result.like}, repost={result.repost}, reply={result.reply}")
            return result
        except Exception as e:
            logger.error(f"[Judge] LLM failed: {e}")
            return JudgmentResult(reason=f'LLM error: {e}')

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
            if extra_context.get('replies'):
                replies = extra_context['replies']
                parts.append(f"\n기존 답글 ({len(replies)}개):")
                for r in replies[:5]:  # 최대 5개만
                    r_user = r.get('user', 'unknown')
                    r_text = (r.get('text', '') or '')[:50]
                    parts.append(f"  - @{r_user}: {r_text}")
                parts.append("(이미 비슷한 내용의 답글이 있으면 reply 안 해도 됨)")

        parts.append("\n어떻게 반응할지 JSON으로 응답하세요.")
        return "\n".join(parts)

    def _parse_response(self, response: str) -> JudgmentResult:
        """LLM 응답 파싱"""
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)

                return JudgmentResult(
                    like=bool(data.get('like', False)),
                    repost=bool(data.get('repost', False)),
                    reply=bool(data.get('reply', False)),
                    reply_type=data.get('reply_type'),
                    confidence=float(data.get('confidence', 0.7)),
                    reason=data.get('reason', '')
                )
        except json.JSONDecodeError:
            pass

        # 파싱 실패 시 텍스트 기반 추론
        result = JudgmentResult(reason='parsed from text')
        if 'like' in response.lower():
            result.like = True
        if 'repost' in response.lower() or 'retweet' in response.lower():
            result.repost = True
        if 'reply' in response.lower():
            result.reply = True

        return result
