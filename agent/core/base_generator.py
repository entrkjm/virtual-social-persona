"""
Base Generator - Common Content Generation Logic
플랫폼/모드 무관 공통 생성 로직
"""
import json
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from core.llm import llm_client
from agent.persona.pattern_tracker import PatternTracker, create_pattern_tracker
from agent.core.text_utils import extract_keywords, calculate_similarity


class ContentMode(Enum):
    CHAT = "chat"
    POST = "post"


@dataclass
class ContentConfig:
    mode: ContentMode
    min_length: int
    max_length: int
    tone: str
    starters: List[str]
    endings: List[str]
    patterns: List[str]


class BaseContentGenerator(ABC):
    """공통 콘텐츠 생성 로직 - 플랫폼별 Generator가 상속"""
    
    def __init__(self, persona_config, platform_config: Optional[Dict] = None):
        self.persona = persona_config
        self.platform_config = platform_config or {}
        self._load_style_configs()
        self._load_review_config()
        self._load_quip_pool()
        self.pattern_tracker = create_pattern_tracker(persona_config)
    
    def _load_quip_pool(self):
        """QUIP 응답용 패턴 풀 로드 (페르소나 설정 우선)"""
        # 1. 플랫폼 모드 설정에서 로드 (가장 우선순위 높음)
        # self.platform_config는 이제 모드별 설정을 포함해야 함
        self.quip_pool = self.platform_config.get('quip_pool', {})
        
        # 2. 페르소나 데이터에서 로드 (identity.yaml 등)
        if not self.quip_pool:
            raw = getattr(self.persona, 'raw_data', {})
            self.quip_pool = raw.get('quip_pool', {})
            
        # 3. 시스템 기본값 (최후의 수단)
        if not self.quip_pool:
            print(f"[GENERATOR] No quip_pool found in config, using system fallback")
            self.quip_pool = {
                'agreement': ['인정', 'ㄹㅇ', '맞음'],
                'impressed': ['오...', '와...'],
                'casual': ['ㅋㅋ', 'ㅎㅎ'],  # 시스템 기본값은 복구 (오버라이드가 작동해야 함)
                'food_related': ['좋아요'],
                'skeptical': ['글쎄요...', '...'],
                'simple_answer': ['네', '아뇨']
            }
        
        speech = getattr(self.persona, 'speech_style', {}) or {}
        self.opener_pool = speech.get('opener_pool', [])
        self.signature_phrases = speech.get('signature_phrases', [])

    def _load_style_configs(self):
        """스타일 설정 로드 - 서브클래스에서 오버라이드 가능"""
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

    def _analyze_recent_posts(self, recent_posts: List[str]) -> Dict:
        """최근 포스트 분석 - 주제/표현 추출 (LLM)"""
        if not recent_posts:
            return {'topics': [], 'openers': [], 'expressions': [], 'tone': ''}

        posts_text = '\n'.join([f'{i+1}. {p}' for i, p in enumerate(recent_posts[:5])])

        prompt = f"""최근 SNS 포스트들을 분석해서 JSON으로 출력하세요.

{posts_text}

다음 형식으로만 출력 (설명 없이 JSON만):
{{
    "topics": ["핵심 주제/소재 3-5개 (예: 아기돼지삼형제, 레시피, 스탠다드)"],
    "openers": ["자주 쓴 시작 표현 2-3개 (예: 혼자 생각해봤거든요, 문득)"],
    "expressions": ["반복되는 특징적 표현 3-5개 (예: 뭉근하게, 텍스처, 나야 들기름)"],
    "tone": "전반적인 톤 한 단어 (예: 센치함/진지함/가벼움/철학적)"
}}"""
        
        try:
            response = llm_client.generate(prompt)
            clean = response.strip()
            if clean.startswith('```'):
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            return json.loads(clean)
        except Exception as e:
            print(f"[DIVERSITY] 분석 실패: {e}")
            return {'topics': [], 'openers': [], 'expressions': [], 'tone': ''}

    def _check_diversity(self, text: str, banned: Dict) -> tuple:
        """다양성 검증 - 통과 못하면 (False, 이유) 반환"""
        text_lower = text.lower()

        for topic in banned.get('topics', []):
            if topic and len(topic) >= 2 and topic.lower() in text_lower:
                return False, f"주제 중복: {topic}"

        first_30 = text[:30]
        for opener in banned.get('openers', []):
            if opener and opener in first_30:
                return False, f"시작 표현 중복: {opener}"

        expr_count = 0
        for expr in banned.get('expressions', []):
            if expr and len(expr) >= 2 and expr in text:
                expr_count += 1
        if expr_count >= 2:
            return False, f"표현 과다 반복: {expr_count}개"

        return True, "OK"

    def _build_anti_repetition_prompt(self, banned: Dict) -> str:
        """다양성 확보를 위한 프롬프트 빌드"""
        if not banned.get('topics') and not banned.get('expressions'):
            return ""
            
        topics_str = ', '.join(banned.get('topics', [])) or '없음'
        openers_str = ' / '.join([f'"{o}"' for o in banned.get('openers', [])]) or '없음'
        exprs_str = ', '.join(banned.get('expressions', [])) or '없음'
        prev_tone = banned.get('tone', '')

        tone_guide = ""
        if prev_tone:
            tone_guide = f"- 최근 톤이 '{prev_tone}'이었으니, 다른 톤(가벼움/유머/실용적 등)으로 시도해보세요"

        return f"""
### 🚫 다양성 규칙 (매우 중요 - 반드시 지켜야 함):

**금지된 주제/소재** (최근에 다뤘음, 절대 언급 금지):
{topics_str}

**금지된 시작 표현** (다른 방식으로 시작하세요):
{openers_str}

**금지된 표현들** (최근 자주 씀, 사용 금지):
{exprs_str}

**다양성 원칙**:
1. 위 주제들과 완전히 다른 새로운 주제로 작성
2. 위 시작 표현 대신 완전히 다른 방식으로 시작 (질문, 감탄, 직접 진입 등)
3. 위 표현들을 하나도 사용하지 않기
{tone_guide}
"""

    def _get_energy_level(self) -> str:
        weights = {'tired': 0.25, 'normal': 0.50, 'excited': 0.25}
        return random.choices(
            list(weights.keys()),
            weights=list(weights.values())
        )[0]

    def _build_style_prompt(self, config: ContentConfig, energy: str) -> str:
        energy_config = self.energy_levels.get(energy, {})
        starters = energy_config.get('starters', config.starters)
        endings = energy_config.get('endings', config.endings)
        
        return f"""
[말투 스타일]
- 톤: {config.tone}
- 문장 시작: {', '.join(starters[:3])}
- 문장 종결: {', '.join(endings[:3])}
- 에너지: {energy}
"""

    def select_quip(self, category: str) -> Optional[str]:
        """QUIP 카테고리에서 랜덤 선택"""
        options = self.quip_pool.get(category, [])
        return random.choice(options) if options else None

    def check_similarity(self, text: str, recent_posts: List[str], threshold: float = 0.35) -> bool:
        """최근 포스트와 유사도 체크 - True면 통과"""
        for recent in recent_posts:
            if calculate_similarity(text, recent) >= threshold:
                return False
        return True

    @abstractmethod
    def generate(self, *args, **kwargs) -> str:
        """서브클래스에서 구현해야 하는 메인 생성 메서드"""
        pass
