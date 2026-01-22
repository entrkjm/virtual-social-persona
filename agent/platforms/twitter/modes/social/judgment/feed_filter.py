"""
Feed Filter
LLM 기반 피드 필터링 (배치 처리)

위험/정치/종교/논란/무관 콘텐츠 제외
+ 이해 불가 콘텐츠 필터링 (content_filter.yaml 기반)
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import yaml
from core.llm import llm_client

logger = logging.getLogger("agent")

# 언어별 패턴
_LANGUAGE_PATTERNS = {
    'ko': re.compile(r'[가-힣]'),
    'en': re.compile(r'[a-zA-Z]{3,}'),
    'ja': re.compile(r'[\u3040-\u309F\u30A0-\u30FF]'),
    'zh': re.compile(r'[\u4e00-\u9fff]'),
    # 하위호환
    'korean': re.compile(r'[가-힣]'),
    'english': re.compile(r'[a-zA-Z]{3,}'),
    'japanese': re.compile(r'[\u3040-\u309F\u30A0-\u30FF]'),
    'chinese': re.compile(r'[\u4e00-\u9fff]'),
}

# 이모지 패턴
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "]+",
    flags=re.UNICODE
)

# 읽을 수 있는 문자 패턴 (한글, 영문, 숫자)
_READABLE_PATTERN = re.compile(r'[가-힣a-zA-Z0-9]')


@dataclass
class FilterResult:
    """필터링 결과"""
    post_id: str
    passed: bool
    reason: str


def _load_content_filter_config(persona_id: str) -> Dict[str, Any]:
    """content_filter.yaml 로드 (없으면 기본값)"""
    config_path = Path(f"personas/{persona_id}/platforms/twitter/content_filter.yaml")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


class FeedFilter:
    """
    LLM 기반 피드 필터링 (배치)

    16개 포스트를 한 번에 보내서 pass/fail 판단
    + Rule-based pre-filter (이해 불가 콘텐츠 사전 제외)
    """

    def __init__(
        self,
        persona_brief: str,
        core_interests: List[str],
        language_filter: Optional[str] = None,
        persona_id: Optional[str] = None
    ):
        """
        Args:
            persona_brief: 페르소나 한줄 설명 (예: "요리사, 음식과 레시피에 관심")
            core_interests: 핵심 관심 키워드
            language_filter: 언어 필터 ("korean", "english", etc.) - None이면 필터 안함
            persona_id: 페르소나 ID (content_filter.yaml 로드용)
        """
        self.persona_brief = persona_brief
        self.core_interests = core_interests
        self.language_filter = language_filter
        self._lang_pattern = _LANGUAGE_PATTERNS.get(language_filter) if language_filter else None

        # content_filter.yaml 로드
        self.content_filter_config = _load_content_filter_config(persona_id) if persona_id else {}
        self.pre_filter_config = self.content_filter_config.get('pre_filter', {})
        self.llm_hints = self.content_filter_config.get('llm_hints', {})

    def _build_system_prompt(self) -> str:
        interests = ", ".join(self.core_interests[:5])

        # LLM 힌트 (content_filter.yaml에서)
        extra_hints = self.llm_hints.get('feed_filter', '')

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
- 이해할 수 없는 언어나 맥락의 포스트
- 외국어 비율이 높아서 의미 파악이 어려운 포스트
{extra_hints}
반드시 아래 JSON 형식으로만 응답하세요:
{{"results": [{{"id": "포스트ID", "pass": true/false, "reason": "짧은 이유"}}]}}"""

    def _rule_based_pre_filter(self, post: Dict[str, Any]) -> Optional[str]:
        """
        Rule-based pre-filter (LLM 호출 전)

        Returns:
            None if passed, reason string if filtered
        """
        if not self.pre_filter_config.get('enabled', True):
            return None

        text = post.get('text', '')

        # 이모지/공백 제거 후 길이 체크
        text_clean = _EMOJI_PATTERN.sub('', text).strip()
        text_clean = re.sub(r'\s+', '', text_clean)

        min_length = self.pre_filter_config.get('min_text_length', 10)
        if len(text_clean) < min_length:
            return f'too_short_{len(text_clean)}'

        # 이모지만 있는 포스트 스킵
        if self.pre_filter_config.get('skip_emoji_only', True):
            if not text_clean:
                return 'emoji_only'

        # 읽을 수 있는 문자 비율 체크
        min_readable_ratio = self.pre_filter_config.get('min_readable_ratio', 0.3)
        readable_chars = len(_READABLE_PATTERN.findall(text))
        total_chars = len(text_clean) if text_clean else 1
        readable_ratio = readable_chars / total_chars

        if readable_ratio < min_readable_ratio:
            return f'unreadable_{readable_ratio:.2f}'

        # 지원 언어 체크
        supported_langs = self.pre_filter_config.get('supported_languages', [])
        if supported_langs:
            has_supported_lang = False
            for lang in supported_langs:
                pattern = _LANGUAGE_PATTERNS.get(lang)
                if pattern and pattern.search(text):
                    has_supported_lang = True
                    break
            if not has_supported_lang:
                return 'unsupported_language'

        # 스킵 패턴 체크
        skip_patterns = self.pre_filter_config.get('skip_patterns', [])
        for pattern in skip_patterns:
            if re.search(pattern, text):
                return f'pattern_{pattern[:10]}'

        return None

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

        results = []
        filtered_posts = []
        pre_filtered_count = 0

        # 0차: Rule-based pre-filter (content_filter.yaml 기반)
        for post in posts:
            post_id = str(post.get('id', ''))
            pre_filter_reason = self._rule_based_pre_filter(post)
            if pre_filter_reason:
                results.append(FilterResult(
                    post_id=post_id,
                    passed=False,
                    reason=pre_filter_reason
                ))
                pre_filtered_count += 1
            else:
                filtered_posts.append(post)

        if pre_filtered_count > 0:
            logger.info(f"[FeedFilter] Pre-filter: {pre_filtered_count}/{len(posts)} filtered")

        if not filtered_posts:
            logger.info(f"[FeedFilter] All {len(posts)} posts pre-filtered")
            return results

        # 1차: 언어 필터 (설정된 경우만, 레거시 호환)
        lang_filtered_posts = []
        if self._lang_pattern:
            for post in filtered_posts:
                post_id = str(post.get('id', ''))
                text = post.get('text', '')
                if not self._lang_pattern.search(text):
                    results.append(FilterResult(
                        post_id=post_id,
                        passed=False,
                        reason=f'no_{self.language_filter}'
                    ))
                else:
                    lang_filtered_posts.append(post)

            if not lang_filtered_posts:
                logger.info(f"[FeedFilter] All remaining posts filtered (no {self.language_filter})")
                return results

            filtered_posts = lang_filtered_posts

        # 포스트 요약 생성
        post_summaries = []
        for i, post in enumerate(filtered_posts):
            post_id = post.get('id', str(i))
            user = post.get('user', 'unknown')
            text = (post.get('text', '')[:100]).replace('\n', ' ')
            post_summaries.append(f"[{post_id}] @{user}: {text}")

        prompt = "다음 포스트들을 필터링해주세요:\n\n" + "\n".join(post_summaries)

        try:
            response = llm_client.generate(prompt, system_prompt=self._build_system_prompt())
            llm_results = self._parse_response(response, filtered_posts)
            # 언어 필터 결과 + LLM 필터 결과 병합
            results.extend(llm_results)
            return results
        except Exception as e:
            logger.error(f"[FeedFilter] LLM failed: {e}")
            # 실패 시 필터 통과한 포스트는 통과 처리
            results.extend([FilterResult(post_id=p.get('id', ''), passed=True, reason='filter_error') for p in filtered_posts])
            return results

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
