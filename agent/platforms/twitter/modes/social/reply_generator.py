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


class SocialReplyGenerator(BaseContentGenerator):
    """Twitter Social Mode - 답글 생성"""
    
    def __init__(self, persona_config, platform_config: Optional[Dict] = None):
        super().__init__(persona_config, platform_config)
        self.formatter = TwitterFormatter(platform_config)
    
    def generate(
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
        
        # PERSONAL: 개인 감상 (전문성 없이)
        if response_type == ResponseType.PERSONAL:
            return self._generate_personal_reply(target_tweet, perception, context)

        # NORMAL: 기존 로직
        return self._generate_normal_reply(target_tweet, perception, context)

    def _generate_short_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """SHORT 응답 (15-50자) - 최소 프롬프트"""
        constraint_prompt = self.formatter.get_constraint_prompt()
        
        def _generate():
            prompt = f"""
{context.get('system_prompt', '')}

상대방 글: "{target_tweet.get('text', '')}"

15~50자 이내로 짧게 반응하세요.
- 자연스럽고 캐주얼하게
{constraint_prompt}
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
        constraint_prompt = self.formatter.get_constraint_prompt()

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
{constraint_prompt}
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
        constraint_prompt = self.formatter.get_constraint_prompt()
        
        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=100, max_length=200,
            tone="열정적이고 전문적인", starters=[], endings=[], patterns=[]
        )

        def _generate():
            energy = 'excited'  # TMI 모드는 항상 excited
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
- 100~200자로 TMI스럽게 설명
- 당신의 전문 지식을 자연스럽게 녹여서
- "아! 그거요?" 같은 반응으로 시작해도 좋음
{constraint_prompt}
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config)

    def _generate_personal_reply(
        self,
        target_tweet: Dict,
        perception: Dict,
        context: Dict
    ) -> str:
        """PERSONAL 응답 (30-80자) - 전문성 없이 개인 감상"""
        constraint_prompt = self.formatter.get_constraint_prompt()
        
        config = ContentConfig(
            mode=ContentMode.CHAT,
            min_length=30, max_length=80,
            tone="캐주얼하고 감상적인", starters=[], endings=[], patterns=[]
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
- 30~80자 정도로 짧게
- "오..." "와..." 같은 감탄사 OK
- 조언이나 팁 금지 (전문 분야 아님)
{constraint_prompt}
"""
            return llm_client.generate(prompt)

        return self._validate_and_regenerate(_generate, config)

    def _validate_and_regenerate(
        self,
        generate_fn,
        config: ContentConfig,
        max_retries: int = 3
    ) -> str:
        """검증 실패 시 재생성"""
        for attempt in range(max_retries):
            text = generate_fn()
            text = self._post_process(text, config)

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
