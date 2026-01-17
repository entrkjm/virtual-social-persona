"""
Content Generator
chat/post 스타일 분리 기반 콘텐츠 생성기
Pattern Tracker 연동으로 말투 패턴 관리
"""
import re
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from core.llm import llm_client
from agent.pattern_tracker import PatternTracker, create_pattern_tracker


def contains_forbidden_chars(text: str) -> bool:
    """한자, 일본어 포함 여부 체크"""
    # CJK Unified Ideographs (한자)
    if re.search(r'[\u4e00-\u9fff]', text):
        return True
    # 히라가나
    if re.search(r'[\u3040-\u309f]', text):
        return True
    # 가타카나
    if re.search(r'[\u30a0-\u30ff]', text):
        return True
    return False


def get_forbidden_chars(text: str) -> List[str]:
    """금지 문자 추출"""
    found = []
    # 한자
    hanzi = re.findall(r'[\u4e00-\u9fff]+', text)
    if hanzi:
        found.extend(hanzi)
    # 히라가나
    hiragana = re.findall(r'[\u3040-\u309f]+', text)
    if hiragana:
        found.extend(hiragana)
    # 가타카나
    katakana = re.findall(r'[\u30a0-\u30ff]+', text)
    if katakana:
        found.extend(katakana)
    return found


class ContentMode(Enum):
    CHAT = "chat"  # 답글/대화
    POST = "post"  # 독립 포스팅


@dataclass
class ContentConfig:
    mode: ContentMode
    min_length: int
    max_length: int
    tone: str
    starters: List[str]
    endings: List[str]
    patterns: List[str]


class ContentGenerator:
    def __init__(self, persona_config):
        self.persona = persona_config
        self._load_style_configs()
        self._load_review_config()
        self.pattern_tracker = create_pattern_tracker(persona_config)

    def _load_style_configs(self):
        speech = self.persona.speech_style or {}

        chat_config = speech.get('chat', {})
        self.chat_config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=chat_config.get('length', {}).get('min', 20),
            max_length=chat_config.get('length', {}).get('max', 140),
            tone=chat_config.get('tone', '친근하고 도움주는'),
            starters=chat_config.get('starters', ['음...', '아...']),
            endings=chat_config.get('endings', ['~요', '~거든요']),
            patterns=chat_config.get('patterns', [])
        )

        post_config = speech.get('post', {})
        self.post_config = ContentConfig(
            mode=ContentMode.POST,
            min_length=post_config.get('length', {}).get('min', 30),
            max_length=post_config.get('length', {}).get('max', 250),
            tone=post_config.get('tone', '짧고 임팩트 있게'),
            starters=post_config.get('starters', ['음...', '갑자기 생각났는데']),
            endings=post_config.get('endings', ['~임', '...']),
            patterns=post_config.get('patterns', [])
        )

        self.energy_levels = speech.get('energy_levels', {})
        self.opener_pool = speech.get('opener_pool', [])
        self.closer_pool = speech.get('closer_pool', [])

    def _load_review_config(self):
        behavior = self.persona.behavior or {}
        review_config = behavior.get('content_review', {})

        self.review_enabled = review_config.get('enabled', False)
        self.review_fix_patterns = review_config.get('fix_excessive_patterns', True)
        self.review_patterns = review_config.get('patterns_to_moderate', [])
        self.review_max_occurrences = review_config.get('max_pattern_occurrences', 1)

    def _get_energy_level(self) -> str:
        weights = {'tired': 0.25, 'normal': 0.50, 'excited': 0.25}
        return random.choices(
            list(weights.keys()),
            weights=list(weights.values())
        )[0]

    def _build_style_prompt(self, config: ContentConfig, energy: str) -> str:
        energy_config = self.energy_levels.get(energy, {})

        return f"""
### 스타일 가이드:
- 톤: {config.tone}
- 에너지: {energy} ({energy_config.get('description', '')})
- 글자수: {config.min_length}~{config.max_length}자 (반드시 준수)
- 문장 시작 예시: {', '.join(config.starters[:3])}
- 문장 끝 예시: {', '.join(config.endings[:3])}

### 문자 규칙:
- 한글만 사용 (알파벳, 일본어 금지)
- 숫자, 특수문자, 이모지는 허용
- 외래어도 한글로 표기 (예: 파스타, 카페)
"""

    def generate_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """답글 생성 (chat 모드) - 검증 포함"""
        config = self.chat_config

        def _generate():
            energy = self._get_energy_level()
            style_prompt = self._build_style_prompt(config, energy)
            warning = self._get_regeneration_warning()

            prompt = f"""
{context.get('system_prompt', '')}

{style_prompt}
{warning}

### 상황:
- 상대방: @{target_tweet.get('user', '')}
- 상대방 글: "{target_tweet.get('text', '')}"
- 감정 분석: {perception.get('sentiment', 'neutral')}
- 의도: {perception.get('intent', '')}
- 주제: {', '.join(perception.get('topics', []))}
- 현재 기분: {context.get('mood', '')}
- 관심사: {', '.join(context.get('interests', []))}

### 지시:
위 상대방의 글에 자연스럽게 답글을 작성하세요.
- {config.min_length}~{config.max_length}자 사이로 작성
- 멘션(@username) 포함 금지
- 페르소나의 말투 특성 반영
- 반드시 한글만 사용 (한자, 일본어 절대 금지)
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config)

    def generate_post(
        self,
        topic: Optional[str] = None,
        inspiration: Optional[Dict] = None,
        context: Dict = None
    ) -> str:
        """독립 포스팅 생성 (post 모드) - 검증 포함"""
        context = context or {}
        config = self.post_config

        def _generate():
            energy = self._get_energy_level()
            style_prompt = self._build_style_prompt(config, energy)
            warning = self._get_regeneration_warning()

            topic_hint = ""
            if topic:
                topic_hint = f"- 주제: {topic}"
            if inspiration:
                topic_hint += f"\n- 영감: {inspiration.get('angle', '')}"

            prompt = f"""
{context.get('system_prompt', '')}

{style_prompt}
{warning}

### 상황:
- 현재 기분: {context.get('mood', '')}
- 관심사: {', '.join(context.get('interests', []))}
{topic_hint}

### 지시:
독백 형태의 트윗을 작성하세요.
- {config.min_length}~{config.max_length}자 사이로 작성
- 혼자 생각을 정리하듯이, 독백 느낌으로
- 페르소나의 말투 특성 반영
- 요리 비유나 음식 관련 통찰 권장
- 반드시 한글만 사용 (한자, 일본어 절대 금지)
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config)

    def _post_process(self, text: str, config: ContentConfig) -> str:
        text = text.strip()
        text = text.strip('"\'')

        if len(text) > config.max_length:
            text = text[:config.max_length - 3] + "..."

        return text

    def _validate_and_regenerate(
        self,
        generate_fn,
        config: ContentConfig,
        max_retries: int = 3
    ) -> str:
        """검증 실패 시 재생성 + 리뷰 레이어"""
        for attempt in range(max_retries):
            text = generate_fn()
            text = self._post_process(text, config)

            forbidden = get_forbidden_chars(text)
            if not forbidden:
                text = self._review_content(text, config)
                return text

            print(f"[CONTENT] 금지 문자 감지 (시도 {attempt + 1}/{max_retries}): {forbidden}")

            if attempt < max_retries - 1:
                self._add_regeneration_warning(forbidden)

        print(f"[CONTENT] 재생성 실패, 마지막 결과 사용")
        return text

    def _add_regeneration_warning(self, forbidden_chars: List[str]):
        """재생성 시 경고 메시지 (다음 생성에 반영)"""
        self._regeneration_warning = f"""
[중요 경고] 이전 응답에 금지 문자가 포함되었습니다: {', '.join(forbidden_chars)}
반드시 한글만 사용하세요. 한자(漢字), 히라가나, 가타카나 절대 금지.
"""

    def _get_regeneration_warning(self) -> str:
        warning = getattr(self, '_regeneration_warning', '')
        self._regeneration_warning = ''
        return warning

    def _review_content(
        self,
        text: str,
        config: ContentConfig,
        topic_context: Optional[str] = None
    ) -> str:
        """LLM 리뷰 레이어: Pattern Tracker 연동 교정"""
        violations = self.pattern_tracker.check_violations(text, topic_context)
        violation_prompt = self.pattern_tracker.format_violations_for_llm(violations)

        if not self.review_enabled and not violations:
            self.pattern_tracker.record_usage(text)
            return text

        patterns_info = ', '.join(self.review_patterns) if self.review_patterns else '~거든요, 음..., 아...'

        prompt = f"""당신은 한국어 글쓰기 교정 전문가입니다.

### 원문:
{text}

{violation_prompt}

### 교정 지시:
1. 위 패턴 위반 사항을 우선 교정하세요
2. 과도하게 반복되는 말투 패턴을 교정하세요
   - 주의 패턴: {patterns_info}
   - 같은 패턴은 최대 {self.review_max_occurrences}회만 허용
3. 자연스러운 일반인의 SNS 글처럼 다듬으세요
   - 너무 연기하는 듯한 말투 → 자연스럽게
   - 과한 감탄사/시작어 → 적절하게
4. 원문의 핵심 의미와 개성은 유지하세요
   - 요리 관련 비유나 표현 유지
   - 전문성이 드러나는 부분 유지
5. 글자 수 유지: {config.min_length}~{config.max_length}자

### 규칙:
- 반드시 한글만 사용 (한자, 일본어 금지)
- 교정된 텍스트만 출력 (설명 없이)
- 원문이 이미 자연스러우면 그대로 출력

### 교정 결과:"""

        reviewed = llm_client.generate(prompt)
        reviewed = reviewed.strip().strip('"\'')

        if contains_forbidden_chars(reviewed):
            print(f"[REVIEW] 리뷰 결과에 금지 문자 포함, 원문 사용")
            self.pattern_tracker.record_usage(text)
            return text

        if len(reviewed) > config.max_length:
            reviewed = reviewed[:config.max_length - 3] + "..."

        self.pattern_tracker.record_usage(reviewed)
        return reviewed


def create_content_generator(persona_config) -> ContentGenerator:
    return ContentGenerator(persona_config)
