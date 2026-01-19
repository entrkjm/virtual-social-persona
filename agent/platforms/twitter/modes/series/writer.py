"""
Content Writer
시리즈 콘텐츠 생성 담당
"""
from typing import Dict, List
from core.llm import llm_client
from config.settings import settings
from agent.persona.persona_loader import PersonaConfig

class ContentWriter:
    def __init__(self, persona: PersonaConfig):
        self.persona = persona

    def write(self, series_name: str, topic: str, template: Dict) -> str:
        """
        시리즈 템플릿 기반 콘텐츠 생성 (YAML 프롬프트 사용)
        """
        # Load custom prompts from YAML
        # 만약 'writer' 키가 있으면 그 안에서 찾고, 없으면 전달된 딕셔너리 자체를 설정으로 봄
        writer_config = template.get('writer', template)
        
        # Support both naming conventions: 'system_prompt'/'user_prompt' OR 'system_template'/'user_template'
        system_key = 'system_prompt' if 'system_prompt' in writer_config else 'system_template'
        user_key = 'user_prompt' if 'user_prompt' in writer_config else 'user_template'
        
        if system_key in writer_config and user_key in writer_config:
            system_prompt = self._build_dynamic_prompt(writer_config[system_key], series_name, topic, template)
            user_prompt = self._build_dynamic_prompt(writer_config[user_key], series_name, topic, template)
        else:
            # Fallback to hardcoded logic if YAML doesn't have writer prompts
            system_prompt = self._build_system_prompt(template)
            user_prompt = self._build_user_prompt(series_name, topic, template)
        
        # LLM 호출
        print(f"[ContentWriter] Generating content for '{topic}' ({series_name})...")
        content = llm_client.generate(user_prompt, system_prompt, model=settings.GEMINI_PRO_MODEL)
        
        return content

    def _build_dynamic_prompt(self, prompt_template: str, series_name: str, topic: str, template: Dict) -> str:
        """Inject variables into YAML string template"""
        try:
            format_type = template.get('format', 'single')
            tone = template.get('tone', '전문적이고 친근한')
            structure = template.get('structure', [])
            structure_text = "\n".join([f"- {s}" for s in structure])
            max_tweets = template.get('max_tweets', 1)
            
            # Speech style endings
            speech_style = self.persona.raw_data.get('speech_style', {}).get('post', {}).get('endings', ['~해요', '~입니다'])
            
            return prompt_template.format(
                persona_name=self.persona.name,
                persona_occupation=self.persona.occupation,
                tone=tone,
                format_type=format_type,
                speech_style=speech_style,
                series_name=series_name,
                topic=topic,
                structure_text=structure_text,
                max_tweets=max_tweets
            )
        except Exception as e:
            print(f"[ContentWriter] Prompt formatting error: {e}")
            return prompt_template # Fallback to raw

    # Legacy methods kept for safety/fallback
    def _build_system_prompt(self, template: Dict) -> str:
        # ... (Same as before, simplified for space or kept as private)
        tone = template.get('tone', '전문적이고 친근한')
        return f"당신은 {self.persona.name}입니다. {tone} 말투로 작성하세요."

    def _build_user_prompt(self, series_name: str, topic: str, template: Dict) -> str:
        return f"주제: [{series_name}] {topic}. 구조에 맞춰 작성하세요."
