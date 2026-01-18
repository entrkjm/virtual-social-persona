"""
Content Generator
chat/post 스타일 분리 기반 콘텐츠 생성기
Pattern Tracker 연동으로 말투 패턴 관리
Response Type 기반 분기 (QUIP/SHORT/NORMAL/LONG)
유사도 기반 중복 방지
"""
import re
import random
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from core.llm import llm_client
from agent.persona.pattern_tracker import PatternTracker, create_pattern_tracker
from agent.core.interaction_intelligence import ResponseType


def extract_keywords(text: str) -> Set[str]:
    """텍스트에서 키워드 추출 (조사 제거 + 2글자 이상)"""
    words = re.findall(r'[가-힣a-zA-Z]{2,}', text)

    stopwords = {
        '오늘', '문득', '그게', '이제', '근데', '그런', '어떤', '뭔가', '진짜', '정말',
        '그냥', '너무', '아주', '매우', '조금', '좀', '많이', '약간', '이런', '저런',
        '하는', '하고', '해서', '했는데', '했어요', '거든요', '같아요', '있어요', '없어요',
        '생각', '느낌', '기분', '마음', '것', '거', '뭐', '왜', '어떻게'
    }

    josa_pattern = r'(이|가|은|는|을|를|의|에|에서|로|으로|와|과|랑|이랑|도|만|까지|부터|처럼|같이|라고|이라고|라는|이라는|란|이란|들|했|하다|하고|해서|에요|예요|이에요|거든요|잖아요|네요|죠|이죠)$'

    keywords = set()
    for w in words:
        if w in stopwords or len(w) < 2:
            continue
        cleaned = re.sub(josa_pattern, '', w)
        if len(cleaned) >= 2:
            keywords.add(cleaned)

    return keywords


def extract_ngrams(text: str, n: int = 3) -> Set[str]:
    """텍스트에서 n-gram 추출 (공백 제거)"""
    text = re.sub(r'[^가-힣a-zA-Z]', '', text)
    if len(text) < n:
        return set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def calculate_similarity(text1: str, text2: str) -> float:
    """키워드 + n-gram 기반 유사도

    두 가지 기준:
    1. 키워드 Jaccard similarity
    2. 공통 4-gram 개수 기반 (5개 이상이면 유사)
    """
    kw1 = extract_keywords(text1)
    kw2 = extract_keywords(text2)

    ng1 = extract_ngrams(text1, 4)
    ng2 = extract_ngrams(text2, 4)

    kw_sim = 0.0
    if kw1 and kw2:
        common_kw = kw1 & kw2
        union = len(kw1 | kw2)
        kw_sim = len(common_kw) / union if union > 0 else 0.0
        if len(common_kw) >= 3:
            kw_sim = max(kw_sim, 0.35)

    ng_sim = 0.0
    if ng1 and ng2:
        common_ng = ng1 & ng2
        if len(common_ng) >= 8:
            ng_sim = 0.5
        elif len(common_ng) >= 5:
            ng_sim = 0.35
        elif len(common_ng) >= 3:
            ng_sim = 0.2

    return max(kw_sim, ng_sim)


def twitter_weighted_len(text: str) -> int:
    """Twitter 가중치 글자수 (한글/한자/일본어 = 2, 나머지 = 1)"""
    count = 0
    for char in text:
        if '\u1100' <= char <= '\u11FF' or '\u3130' <= char <= '\u318F' or '\uAC00' <= char <= '\uD7AF':
            count += 2
        elif '\u4E00' <= char <= '\u9FFF' or '\u3040' <= char <= '\u30FF':
            count += 2
        else:
            count += 1
    return count


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
        self._load_quip_pool()
        self.pattern_tracker = create_pattern_tracker(persona_config)

    def _load_quip_pool(self):
        """QUIP 응답용 패턴 풀 로드"""
        raw = getattr(self.persona, 'raw_data', {})
        self.quip_pool = raw.get('quip_pool', {})
        if not self.quip_pool:
            self.quip_pool = {
                'agreement': ['인정', 'ㄹㅇ', '맞음'],
                'impressed': ['오...', '와...'],
                'casual': ['ㅋㅋ', 'ㅎㅎ'],
                'food_related': ['좋아요'],
                'skeptical': ['글쎄요...', '...'],
                'simple_answer': ['네', '아뇨']
            }

        speech = getattr(self.persona, 'speech_style', {}) or {}
        self.opener_pool = speech.get('opener_pool', [])
        self.signature_phrases = speech.get('signature_phrases', [])

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

    def select_quip(self, category: str) -> str:
        """QUIP 카테고리에서 랜덤 선택"""
        pool = self.quip_pool.get(category, [])
        if not pool:
            pool = self.quip_pool.get('casual', ['음...'])
        return random.choice(pool)

    def generate_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """답글 생성 - response_type 기반 분기"""
        response_type = perception.get('response_type', ResponseType.NORMAL)

        # QUIP: LLM 없이 패턴 풀에서 선택
        if response_type == ResponseType.QUIP:
            category = perception.get('quip_category', 'casual')
            quip = self.select_quip(category)
            print(f"[CONTENT] QUIP response: {quip} (category={category})")
            return quip

        # SHORT: 간단 프롬프트
        if response_type == ResponseType.SHORT:
            return self._generate_short_reply(target_tweet, perception, context)

        # LONG: TMI 모드 (전문 분야 주제)
        if response_type == ResponseType.LONG:
            return self._generate_long_reply(target_tweet, perception, context)

        # NORMAL: 기존 로직
        return self._generate_normal_reply(target_tweet, perception, context)

    def _generate_short_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """SHORT 응답 (15-50자) - 최소 프롬프트"""
        def _generate():
            prompt = f"""
{context.get('system_prompt', '')}

상대방 글: "{target_tweet.get('text', '')}"

15~50자 이내로 짧게 반응하세요.
- 자연스럽고 캐주얼하게
- 한글만 사용
- 설명 없이 답글만 출력
"""
            return llm_client.generate(prompt)

        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=15, max_length=50,
            tone="캐주얼", starters=[], endings=[], patterns=[]
        )
        return self._validate_and_regenerate(_generate, config)

    def _generate_normal_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """NORMAL 응답 (50-100자) - 기존 chat 모드"""
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

    def _generate_long_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """LONG 응답 (100+자) - 전문 분야 TMI 모드"""
        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=80, max_length=140,
            tone="열정적이고 디테일한",
            starters=self.chat_config.starters,
            endings=self.chat_config.endings,
            patterns=[]
        )

        def _generate():
            prompt = f"""
{context.get('system_prompt', '')}

### 상황:
- 상대방: @{target_tweet.get('user', '')}
- 상대방 글: "{target_tweet.get('text', '')}"
- 주제: {', '.join(perception.get('topics', []))}
- 전문 분야 관련도: 높음

### 지시:
{self.persona.identity}로서 전문적인 관점으로 자세히 답변하세요.
- 80~140자로 작성
- 전문 분야 팁이나 디테일한 정보 포함
- 열정적이지만 페르소나 말투 유지
- 한글만 사용
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config)

    def generate_post(
        self,
        topic: Optional[str] = None,
        inspiration: Optional[Dict] = None,
        context: Dict = None,
        recent_posts: List[str] = None
    ) -> str:
        """독립 포스팅 생성 (post 모드) - 검증 + 유사도 체크 포함"""
        context = context or {}
        recent_posts = recent_posts or []
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

            topic_context = context.get('topic_context', '')
            context_hint = f"\n- 배경지식: {topic_context}" if topic_context else ""

            anti_repetition = ""
            if recent_posts:
                recent_summary = "\n".join([f"  - {p[:50]}..." if len(p) > 50 else f"  - {p}" for p in recent_posts[:5]])

                all_recent_keywords = set()
                for p in recent_posts:
                    all_recent_keywords.update(extract_keywords(p))
                banned_words = sorted(all_recent_keywords)[:15]

                banned_openers = self.opener_pool[:5] if self.opener_pool else []
                banned_openers_str = ' / '.join([f'"{o}"' for o in banned_openers]) if banned_openers else '없음'

                anti_repetition = f"""
### ⚠️ 중복 방지 (매우 중요 - 반드시 지켜야 함):
최근 내가 쓴 글들:
{recent_summary}

**금지된 단어들** (최근 사용함, 절대 쓰지 마세요):
{', '.join(banned_words)}

**금지된 시작 패턴** (다른 방식으로 시작하세요):
{banned_openers_str}

**작성 원칙**:
1. 위 금지 단어를 하나도 쓰지 않기
2. 완전히 새로운 주제로 작성
3. 다른 시작 패턴 사용
"""

            prompt = f"""
{context.get('system_prompt', '')}

{style_prompt}
{warning}
{anti_repetition}

### 상황:
- 현재 기분: {context.get('mood', '')}
- 관심사: {', '.join(context.get('interests', []))}
{topic_hint}{context_hint}

### 지시:
독백 형태의 트윗을 작성하세요.
- {config.min_length}~{config.max_length}자 사이로 작성
- 혼자 생각을 정리하듯이, 독백 느낌으로
- 페르소나의 말투 특성 반영
- 배경지식이 있으면 참고하되, 내 관점으로 표현
- 반드시 한글만 사용 (한자, 일본어 절대 금지)
- 최근 글과 다른 새로운 내용으로 작성
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate_post(_generate, config, recent_posts)

    def _post_process(self, text: str, config: ContentConfig) -> str:
        text = text.strip()
        text = text.strip('"\'')

        if len(text) > config.max_length:
            text = text[:config.max_length - 3] + "..."

        weighted = twitter_weighted_len(text)
        if weighted > 280:
            target_chars = len(text) * 270 // weighted
            text = text[:target_chars] + "..."

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

    def _validate_and_regenerate_post(
        self,
        generate_fn,
        config: ContentConfig,
        recent_posts: List[str],
        max_retries: int = 5,
        similarity_threshold: float = 0.3
    ) -> str:
        """포스트 전용 검증: 금지 문자 + 유사도 체크 + 리뷰"""
        for attempt in range(max_retries):
            text = generate_fn()
            text = self._post_process(text, config)

            forbidden = get_forbidden_chars(text)
            if forbidden:
                print(f"[CONTENT] 금지 문자 감지 (시도 {attempt + 1}/{max_retries}): {forbidden}")
                if attempt < max_retries - 1:
                    self._add_regeneration_warning(forbidden)
                continue

            max_sim = 0.0
            most_similar = ""
            for recent in recent_posts:
                sim = calculate_similarity(text, recent)
                if sim > max_sim:
                    max_sim = sim
                    most_similar = recent[:50]

            if max_sim > similarity_threshold:
                print(f"[CONTENT] 유사도 높음 {max_sim:.2f} (시도 {attempt + 1}/{max_retries})")
                print(f"  - 생성: {text[:50]}...")
                print(f"  - 유사: {most_similar}...")
                if attempt < max_retries - 1:
                    self._add_similarity_warning(most_similar)
                continue

            text = self._review_content(text, config)
            print(f"[CONTENT] 포스트 생성 성공 (유사도 {max_sim:.2f})")
            return text

        print(f"[CONTENT] 재생성 실패, 마지막 결과 사용")
        return text

    def _add_similarity_warning(self, similar_text: str):
        """유사도 경고 추가"""
        self._regeneration_warning = f"""
[중요 경고] 이전 응답이 최근 글과 너무 비슷합니다.
비슷한 글: "{similar_text}..."
완전히 다른 주제/관점/표현을 사용하세요.
"""

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
        """LLM 리뷰 레이어: Pattern Tracker 연동 + 페르소나 보존 교정"""
        violations = self.pattern_tracker.check_violations(text, topic_context)
        violation_prompt = self.pattern_tracker.format_violations_for_llm(violations)
        persona_prompt = self.pattern_tracker.get_persona_preservation_prompt()

        if not self.review_enabled and not violations:
            self.pattern_tracker.record_usage(text)
            return text

        prompt = f"""당신은 SNS 글쓰기 교정 전문가입니다.
이 페르소나의 개성을 유지하면서 과도한 반복만 줄여야 합니다.

{persona_prompt}

### 원문:
{text}

{violation_prompt}

### 교정 원칙:
1. **페르소나 보존 우선**: 위 "패턴 보존 규칙"을 반드시 따르세요
2. **위반 사항만 교정**: 패턴 위반이 있다면 그것만 고치세요
3. **최소 개입**: 위반이 없으면 원문 그대로 출력하세요
4. **개성 유지**: 어눌함, 망설임 등 페르소나 특성은 제거하지 마세요

### 규칙:
- 반드시 한글만 사용 (한자, 일본어 금지)
- 교정된 텍스트만 출력 (설명 없이)
- 글자 수: {config.min_length}~{config.max_length}자

### 교정 결과:"""

        reviewed = llm_client.generate(prompt)
        reviewed = reviewed.strip().strip('"\'')

        if contains_forbidden_chars(reviewed):
            print(f"[REVIEW] 리뷰 결과에 금지 문자 포함, 원문 사용")
            self.pattern_tracker.record_usage(text)
            return text

        if len(reviewed) > config.max_length:
            reviewed = reviewed[:config.max_length - 3] + "..."

        weighted = twitter_weighted_len(reviewed)
        if weighted > 280:
            target_chars = len(reviewed) * 270 // weighted
            reviewed = reviewed[:target_chars] + "..."

        self.pattern_tracker.record_usage(reviewed)
        return reviewed


def create_content_generator(persona_config) -> ContentGenerator:
    return ContentGenerator(persona_config)
