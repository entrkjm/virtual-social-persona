"""
Feed Filter
LLM 기반 피드 필터링 (배치 처리)

위험/정치/종교/논란/무관 콘텐츠 제외
"""
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.llm import llm_client

logger = logging.getLogger("agent")


@dataclass
class FilterResult:
    """필터링 결과"""
    post_id: str
    passed: bool
    reason: str


class FeedFilter:
    """
    LLM 기반 피드 필터링 (배치)

    16개 포스트를 한 번에 보내서 pass/fail 판단
    """

    def __init__(self, persona_brief: str, core_interests: List[str]):
        """
        Args:
            persona_brief: 페르소나 한줄 설명 (예: "요리사, 음식과 레시피에 관심")
            core_interests: 핵심 관심 키워드
        """
        self.persona_brief = persona_brief
        self.core_interests = core_interests

    def _build_system_prompt(self) -> str:
        interests = ", ".join(self.core_interests[:5])
        return f"""당신은 소셜 미디어 콘텐츠 필터입니다.

페르소나: {self.persona_brief}
관심 분야: {interests}

각 포스트가 이 페르소나가 반응해도 되는 콘텐츠인지 판단하세요.

통과 기준:
- 페르소나의 관심 분야와 관련됨
- 일상적이고 무해한 콘텐츠
- 긍정적이거나 중립적인 톤

제외 기준:
- 정치적 주장이나 논쟁
- 종교적 내용
- 위험하거나 불법적인 내용
- 혐오/차별 발언
- 노골적인 광고/스팸
- 페르소나와 전혀 무관한 전문 분야 (암호화폐, 주식 투자 등)

반드시 아래 JSON 형식으로만 응답하세요:
{{"results": [{{"id": "포스트ID", "pass": true/false, "reason": "짧은 이유"}}]}}"""

    def filter_batch(self, posts: List[Dict[str, Any]]) -> List[FilterResult]:
        """
        배치 필터링

        Args:
            posts: 포스트 목록 [{"id": str, "user": str, "text": str}, ...]

        Returns:
            FilterResult 목록
        """
        if not posts:
            return []

        # 포스트 요약 생성
        post_summaries = []
        for i, post in enumerate(posts):
            post_id = post.get('id', str(i))
            user = post.get('user', 'unknown')
            text = (post.get('text', '')[:100]).replace('\n', ' ')
            post_summaries.append(f"[{post_id}] @{user}: {text}")

        prompt = "다음 포스트들을 필터링해주세요:\n\n" + "\n".join(post_summaries)

        try:
            response = llm_client.generate(prompt, system_prompt=self._build_system_prompt())
            return self._parse_response(response, posts)
        except Exception as e:
            logger.error(f"[FeedFilter] LLM failed: {e}")
            # 실패 시 모두 통과 처리
            return [FilterResult(post_id=p.get('id', ''), passed=True, reason='filter_error') for p in posts]

    def _parse_response(self, response: str, posts: List[Dict]) -> List[FilterResult]:
        """LLM 응답 파싱"""
        try:
            # JSON 추출
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found")

            data = json.loads(response[start:end])
            results_data = data.get('results', [])

            # ID → 결과 매핑
            result_map = {str(r.get('id', '')): r for r in results_data}

            results = []
            for post in posts:
                post_id = str(post.get('id', ''))
                if post_id in result_map:
                    r = result_map[post_id]
                    results.append(FilterResult(
                        post_id=post_id,
                        passed=r.get('pass', True),
                        reason=r.get('reason', '')
                    ))
                else:
                    # LLM이 누락한 포스트는 통과 처리
                    results.append(FilterResult(
                        post_id=post_id,
                        passed=True,
                        reason='not_evaluated'
                    ))

            passed_count = sum(1 for r in results if r.passed)
            logger.info(f"[FeedFilter] {passed_count}/{len(results)} posts passed")

            return results

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[FeedFilter] Parse failed: {e}, passing all")
            return [FilterResult(post_id=p.get('id', ''), passed=True, reason='parse_error') for p in posts]


# Singleton for reuse
_filter_instance: Optional[FeedFilter] = None


def get_feed_filter(persona_brief: str, core_interests: List[str]) -> FeedFilter:
    """FeedFilter 인스턴스 가져오기"""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = FeedFilter(persona_brief, core_interests)
    return _filter_instance
