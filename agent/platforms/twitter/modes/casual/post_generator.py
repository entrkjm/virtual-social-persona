"""
Casual Post Generator - Twitter
Twitter 독립 포스팅(독백) 생성기
"""
from typing import Dict, List, Optional

from core.llm import llm_client
from agent.core.base_generator import BaseContentGenerator, ContentConfig, ContentMode
from agent.platforms.twitter.formatter import TwitterFormatter


class CasualPostGenerator(BaseContentGenerator):
    """Twitter Casual Mode - 독립 포스팅 생성"""
    
    def __init__(self, persona_config, platform_config: Optional[Dict] = None):
        super().__init__(persona_config, platform_config)
        self.formatter = TwitterFormatter(platform_config)
    
    def generate(
        self,
        topic: Optional[str] = None,
        inspiration: Optional[Dict] = None,
        context: Dict = None,
        recent_posts: List[str] = None
    ) -> str:
        """독립 포스팅 생성 (post 모드) - 다양성 검증 + 유사도 체크 포함"""
        context = context or {}
        recent_posts = recent_posts or []
        config = self.post_config
        
        # LLM으로 최근 포스트 분석 (주제/표현 추출)
        banned = self._analyze_recent_posts(recent_posts)
        if banned.get('topics') or banned.get('expressions'):
            print(f"[DIVERSITY] 금지 주제: {banned.get('topics', [])}")
            print(f"[DIVERSITY] 금지 표현: {banned.get('expressions', [])}")

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

            # LLM 분석 기반 다양성 프롬프트
            anti_repetition = self._build_anti_repetition_prompt(banned)
            
            # 플랫폼 제약 조건을 formatter에서 가져옴
            constraint_prompt = self.formatter.get_constraint_prompt()

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
- 페르소나의 말투 특성 반영하되, 새로운 표현 시도
- 배경지식이 있으면 참고하되, 내 관점으로 표현
{constraint_prompt}
- 🔥 최근 글들과 확실히 다른 새로운 내용과 표현으로 작성
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate_post(_generate, config, recent_posts, banned)
    
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

    def _get_regeneration_warning(self) -> str:
        """재생성 경고 메시지"""
        return ""

    def _validate_and_regenerate_post(
        self,
        generate_fn,
        config: ContentConfig,
        recent_posts: List[str],
        banned: Dict,
        max_retries: int = 3
    ) -> str:
        """검증 실패 시 재생성"""
        for attempt in range(max_retries):
            text = generate_fn()
            text = self._post_process(text, config)

            # 금지 문자 체크
            forbidden = self.formatter.check_forbidden(text)
            if forbidden:
                print(f"[CONTENT] 금지 문자 감지 (시도 {attempt + 1}/{max_retries}): {forbidden}")
                continue
            
            # 다양성 체크
            is_diverse, reason = self._check_diversity(text, banned)
            if not is_diverse:
                print(f"[DIVERSITY] 다양성 실패 (시도 {attempt + 1}/{max_retries}): {reason}")
                continue
            
            # 유사도 체크
            if not self.check_similarity(text, recent_posts):
                print(f"[SIMILARITY] 유사도 높음 (시도 {attempt + 1}/{max_retries})")
                continue
            
            return text
        
        # 최종 폴백
        return generate_fn()
    
    def _post_process(self, text: str, config: ContentConfig) -> str:
        """후처리 - 플랫폼 제약 적용"""
        text = text.strip()
        text = text.strip('"\'')

        if len(text) > config.max_length:
            text = text[:config.max_length - 3] + "..."

        # 플랫폼 제약 적용
        text = self.formatter.apply_constraints(text)
        
        return text
