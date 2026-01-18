"""
Content Writer
시리즈 콘텐츠 생성 담당
"""
from typing import Dict, List
from core.llm import llm_client
from agent.persona.persona_loader import PersonaConfig

class ContentWriter:
    def __init__(self, persona: PersonaConfig):
        self.persona = persona

    def write(self, series_name: str, topic: str, template: Dict) -> str:
        """
        시리즈 템플릿 기반 콘텐츠 생성
        """
        system_prompt = self._build_system_prompt(template)
        user_prompt = self._build_user_prompt(series_name, topic, template)
        
        # LLM 호출
        print(f"[ContentWriter] Generating content for '{topic}' ({series_name})...")
        content = llm_client.generate(user_prompt, system_prompt)
        
        # 후처리 (필요 시)
        # 예: 큰따옴표 제거, 마크다운 정리 등
        
        return content

    def _build_system_prompt(self, template: Dict) -> str:
        tone = template.get('tone', '전문적이고 친근한')
        format_type = template.get('format', 'single')
        
        prompt = f"""당신은 '{self.persona.name}'입니다.
직업: {self.persona.occupation}
성격: {template.get('tone', tone)}

당신은 지금 소셜 미디어에 올릴 '시그니처 시리즈' 콘텐츠를 작성하고 있습니다.
독자들이 흥미를 느끼고 유용한 정보를 얻을 수 있도록 깊이 있는 내용을 작성해주세요.

[형식 가이드]
- 형식: {format_type} (스레드 또는 단일 게시물)
- 말투: {self.persona.raw_data.get('speech_style', {}).get('post', {}).get('endings', ['~해요', '~입니다'])} 등을 자연스럽게 사용
- 금지: #해시태그 남발, 이모지 과다 사용, 기계적인 말투
"""
        return prompt

    def _build_user_prompt(self, series_name: str, topic: str, template: Dict) -> str:
        structure = template.get('structure', [])
        structure_text = "\n".join([f"- {s}" for s in structure])
        
        max_tweets = template.get('max_tweets', 1)
        
        prompt = f"""
주제: [{series_name}] {topic}

다음 구조에 맞춰서 글을 작성해주세요:
{structure_text}

[제약 사항]
1. 총 {max_tweets}개의 트윗(타래)으로 나눌 수 있도록 길이를 조절하세요.
2. 각 파트는 명확하게 구분되도록 작성하세요.
3. 첫 문장은 독자의 주의를 끌 수 있는 훅(Hook)으로 시작하세요.
4. 전문적인 지식을 담되, 일반인도 이해하기 쉽게 설명하세요.
"""
        return prompt
