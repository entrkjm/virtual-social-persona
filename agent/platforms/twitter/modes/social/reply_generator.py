"""
Social Reply Generator - Twitter
Twitter 답글/상호작용 생성기
"""
import random
from typing import Dict, List, Optional

from core.llm import llm_client
from agent.core.base_generator import BaseContentGenerator, ContentConfig, ContentMode
from agent.core.interaction_intelligence import ResponseType
from agent.platforms.twitter.formatter import TwitterFormatter
from agent.platforms.twitter.modes.social.reviewer import SocialReplyReviewer


class SocialReplyGenerator(BaseContentGenerator):
    """Twitter Social Mode - 답글 생성"""

    def __init__(self, persona_config, platform_config: Optional[Dict] = None):
        super().__init__(persona_config, platform_config)
        self.formatter = TwitterFormatter(platform_config)
        review_config = self.platform_config.get('review', {})
        self.reviewer = SocialReplyReviewer(persona_config, review_config)
        self._load_constraints()

    def _load_constraints(self):
        """YAML에서 전문가 프레이밍 제약 및 응답 타입 설정 로드"""
        constraints = self.platform_config.get('constraints', {})
        self.avoid_expert_phrases = constraints.get('avoid_expert_phrases', [])
        self.friendly_alternative = constraints.get('friendly_alternative', '저는 이렇게 해요')

        response_types = self.platform_config.get('response_types', {})
        self.response_type_configs = {
            'short': response_types.get('short', {'min_length': 15, 'max_length': 50, 'tone': '캐주얼'}),
            'normal': response_types.get('normal', {'min_length': 50, 'max_length': 100, 'tone': '친근하고 도움주는'}),
            'long': response_types.get('long', {'min_length': 100, 'max_length': 200, 'tone': '열정적이고 전문적인', 'default_energy': 'excited'}),
            'personal': response_types.get('personal', {'min_length': 30, 'max_length': 80, 'tone': '캐주얼하고 감상적인'}),
        }

    def _get_avoid_phrases_text(self) -> str:
        """프롬프트용 회피 문구 텍스트 생성"""
        if not self.avoid_expert_phrases:
            return '"전문가로서..."'
        return ', '.join([f'"{p}"' for p in self.avoid_expert_phrases[:2]])

    def _get_friendly_alternative(self) -> str:
        """친근한 대안 문구 반환"""
        return self.friendly_alternative
    
    def generate(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict,
        recent_replies: List[str] = None
    ) -> str:
        """답글 생성 - response_type 기반 분기"""
        recent_replies = recent_replies or []
        
        # Diversity Check (LLM Analysis)
        banned = self._analyze_recent_posts(recent_replies)
        if banned.get('topics') or banned.get('expressions'):
            print(f"[DIVERSITY] 금지 주제: {banned.get('topics', [])}")
        response_type = perception.get('response_type', ResponseType.NORMAL)

        # QUIP: LLM 없이 패턴 풀에서 선택
        if response_type == ResponseType.QUIP:
            category = perception.get('quip_category', 'casual')
            quip = self.select_quip(category)
            print(f"[CONTENT] QUIP response: {quip} (category={category})")
            return quip

        # SHORT: 간단 프롬프트
        if response_type == ResponseType.SHORT:
            return self._generate_short_reply(target_tweet, perception, context, banned)

        # LONG: TMI 모드 (전문 분야 주제)
        if response_type == ResponseType.LONG:
            return self._generate_long_reply(target_tweet, perception, context)
        
        # PERSONAL: 개인 감상 (전문성 없이)
        if response_type == ResponseType.PERSONAL:
            return self._generate_personal_reply(target_tweet, perception, context)

        # NORMAL: 기존 로직
        return self._generate_normal_reply(target_tweet, perception, context, banned)

    def _generate_short_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict,
        banned: Dict
    ) -> str:
        """SHORT 응답 - 최소 프롬프트"""
        type_config = self.response_type_configs['short']
        min_len, max_len = type_config['min_length'], type_config['max_length']
        tone = type_config['tone']

        constraint_prompt = self.formatter.get_constraint_prompt()
        anti_repetition = self._build_anti_repetition_prompt(banned)

        def _generate():
            prompt = f"""
{context.get('system_prompt', '')}

상대방 글: "{target_tweet.get('text', '')}"

{min_len}~{max_len}자 이내로 짧게 반응하세요.
- 자연스럽고 {tone}하게
{constraint_prompt}
{anti_repetition}
- 설명 없이 답글만 출력
"""
            return llm_client.generate(prompt)

        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=min_len, max_length=max_len,
            tone=tone, starters=[], endings=[], patterns=[]
        )
        return self._validate_and_regenerate(_generate, config, banned=banned, target_text=target_tweet.get('text', ''))

    def _generate_normal_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict,
        banned: Dict
    ) -> str:
        """NORMAL 응답 (50-100자) - 기존 chat 모드"""
        config = self.chat_config
        constraint_prompt = self.formatter.get_constraint_prompt()
        anti_repetition = self._build_anti_repetition_prompt(banned)

        def _generate():
            energy = self._get_energy_level()
            style_prompt = self._build_style_prompt(config, energy)

            prompt = f"""
{context.get('system_prompt', '')}

{style_prompt}

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
- [중요] 전문가 티 내지 말고 친근한 이웃처럼 반응하세요. {self._get_avoid_phrases_text()} 같은 발언 자제.
- 팁을 주더라도 "{self._get_friendly_alternative()}" 정도로 가볍게.
{constraint_prompt}
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config, target_text=target_tweet.get('text', ''))

    def _generate_long_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """LONG 응답 - 전문 분야 TMI 모드"""
        type_config = self.response_type_configs['long']
        min_len, max_len = type_config['min_length'], type_config['max_length']
        tone = type_config['tone']
        default_energy = type_config.get('default_energy', 'excited')

        constraint_prompt = self.formatter.get_constraint_prompt()

        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=min_len, max_length=max_len,
            tone=tone, starters=[], endings=[], patterns=[]
        )

        def _generate():
            energy = default_energy
            style_prompt = self._build_style_prompt(config, energy)
            domain = getattr(self.persona, 'domain', None)
            domain_name = domain.name if domain else '전문 분야'

            prompt = f"""
{context.get('system_prompt', '')}

{style_prompt}

### 상황:
- 상대방: @{target_tweet.get('user', '')}
- 상대방 글: "{target_tweet.get('text', '')}"
- 주제: {', '.join(perception.get('topics', []))}
- 이 주제는 당신의 전문 분야({domain_name})와 관련이 있습니다!

### 지시:
전문가로서 열정을 담아 상세하게 답글을 작성하세요.
- {min_len}~{max_len}자로 TMI스럽게 설명
- 당신의 전문 지식을 자연스럽게 녹여서
- "아! 그거요?" 같은 반응으로 시작해도 좋음
{constraint_prompt}
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config, target_text=target_tweet.get('text', ''))

    def _generate_personal_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """PERSONAL 응답 - 전문성 없이 개인 감상"""
        type_config = self.response_type_configs['personal']
        min_len, max_len = type_config['min_length'], type_config['max_length']
        tone = type_config['tone']

        constraint_prompt = self.formatter.get_constraint_prompt()

        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=min_len, max_length=max_len,
            tone=tone, starters=[], endings=[], patterns=[]
        )

        def _generate():
            prompt = f"""
{context.get('system_prompt', '')}

### 상황:
- 상대방 글: "{target_tweet.get('text', '')}"
- 이 주제는 당신의 전문 분야가 아닙니다.
- 하지만 개인적인 느낌이나 감상을 공유할 수 있습니다.

### 지시:
전문가 코스프레 없이 개인적인 감상만 표현하세요.
- {min_len}~{max_len}자 정도로 짧게
- "오..." "와..." 같은 감탄사 OK
- 조언이나 팁 금지 (전문 분야 아님)
{constraint_prompt}
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config, target_text=target_tweet.get('text', ''))

    def _validate_and_regenerate(
        self,
        generate_fn,
        config: ContentConfig,
        max_retries: int = 3,
        target_text: str = "",
        banned: Dict = None
    ) -> str:
        """검증 실패 시 재생성"""
        banned = banned or {}
        
        for attempt in range(max_retries):
            text = generate_fn()
            text = self._post_process(text, config)

            # [NEW] Check Diversity
            if banned:
                is_diverse, reason = self._check_diversity(text, banned)
                if not is_diverse:
                    print(f"[DIVERSITY] 다양성 실패 (시도 {attempt + 1}/{max_retries}): {reason}")
                    continue

            # [NEW] Reviewer Check
            if target_text:
                text = self.reviewer.review_reply(target_text, text)


            forbidden = self.formatter.check_forbidden(text)
            if not forbidden:
                return text

            print(f"[CONTENT] 금지 문자 감지 (시도 {attempt + 1}/{max_retries}): {forbidden}")

        # 최종 폴백
        return generate_fn()

    def _post_process(self, text: str, config: ContentConfig) -> str:
        """후처리 - 플랫폼 제약 적용"""
        text = text.strip()
        text = text.strip('"\'')

        if len(text) > config.max_length:
            text = text[:config.max_length - 3] + "..."

        text = self.formatter.apply_constraints(text)
        
        return text
