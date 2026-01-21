"""
Image Generator (Vertex AI Imagen)
"""
import os
from typing import List, Optional
try:
    import vertexai
    from vertexai.preview.vision_models import ImageGenerationModel
except ImportError:
    vertexai = None
    ImageGenerationModel = None

from config.settings import settings

class ImageGenerator:
    def __init__(self):
        self.model = None
        if settings.USE_VERTEX_AI and vertexai:
            try:
                vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
                self.model = ImageGenerationModel.from_pretrained(settings.IMAGEN_MODEL)
                print(f"[ImageGenerator] Loaded model: {settings.IMAGEN_MODEL}")
            except Exception as e:
                print(f"[ImageGenerator] Init failed: {e}")
        else:
            print("[ImageGenerator] Vertex AI disabled or package missing.")

    def generate(self, prompt: str, count: int = 4) -> List[bytes]:
        """이미지 생성 -> bytes 리스트 반환"""
        if not self.model:
            return []
            
        print(f"[ImageGenerator] Generating {count} images for: {prompt[:50]}...")
        try:
            # Imagen 3 API Call
            response = self.model.generate_images(
                prompt=prompt,
                number_of_images=count,
                # aspect_ratio="1:1", or "4:5" for portrait
                language="en",
                # person_generation="allow_adult",
                # safety_filter_level="block_medium_and_above"
            )
            
            # 저장하지 않고 bytes로 반환 (나중에 아카이버가 저장)
            return [img._image_bytes for img in response.images]
            
        except Exception as e:
            print(f"[ImageGenerator] Generation Error: {e}")
            return []

    def create_dynamic_prompts(self, topic: str, context_str: str, prompt_guide: dict) -> List[str]:
        """LLM을 사용하여 4개의 각기 다른 연출 프롬프트 생성 (스마트폰 스타일)"""
        from core.llm import llm_client
        import json

        # Art Director 설정 (YAML에서 로드)
        art_director = prompt_guide.get('art_director', {})
        ad_role = art_director.get('role', 'Art Director specializing in CANDID photography')
        ad_goal = art_director.get('goal', 'create prompts that look like candid smartphone photos')
        self._domain_context = art_director.get('domain_context', 'subject')
        self._setting_examples = art_director.get('setting_examples', ['indoor setting'])

        guide_json = json.dumps(prompt_guide, indent=2, ensure_ascii=False)

        # style_prefix가 있으면 사용
        style_prefix = prompt_guide.get('style_prefix', 'Candid smartphone photo, unedited, raw')
        negative_prompts = prompt_guide.get('negative_prompts', '')

        prompt = f"""
You are an {ad_role}.
Your goal is to {ad_goal}.

IMPORTANT: "Smartphone photo" means the STYLE of the photo (casual, unedited) - DO NOT include any smartphone or phone device in the actual image!

Generate 4 DISTINCT prompt variations for: "{topic}"
Context: {context_str}

CRITICAL STYLE REQUIREMENTS:
1. Every prompt MUST start with: "{style_prefix}"
2. Emphasize IMPERFECTIONS: messy table, uneven lighting, not perfectly composed
3. Use casual angles like someone hastily snapped a photo before eating
4. Include realistic flaws: slight blur, grain, uneven focus, background clutter
5. DO NOT show any phone, smartphone, or hands holding devices in the image

AVOID THESE (negative): {negative_prompts}

Reference Guide for keywords:
{guide_json}

CREATE 4 CONCEPTS:
1. Quick snapshot before eating (slightly blurred, steam visible)
2. Overhead phone shot (flat lay but messy, not styled)
3. Candid side angle (natural window light, cluttered background)
4. Close-up detail (macro but with phone camera limitations)

OUTPUT FORMAT: valid JSON list of 4 strings only. No other text.
Each prompt should be 1-2 sentences describing the EXACT shot.

Example:
[
  "Candid smartphone photo, iPhone shot, steaming hot {topic} in a mismatched bowl, 45-degree angle, natural window light, sauce splatters on wooden table, slightly out of focus background, no editing",
  ...
]
"""
        try:
            response = llm_client.generate(prompt, model=settings.GEMINI_PRO_MODEL)
            clean_res = response.strip()
            if clean_res.startswith('```'):
                clean_res = clean_res.split('```')[1]
            if clean_res.startswith('json'):
                clean_res = clean_res[4:]
            
            prompts = json.loads(clean_res)
            return prompts[:4] if isinstance(prompts, list) else []
            
        except Exception as e:
            print(f"[ImageGenerator] Dynamic Prompt Logic Failed: {e}")
            # Fallback: YAML 설정 기반 동적 생성
            setting = self._setting_examples[0] if self._setting_examples else 'indoor setting'
            return [
                f"Candid smartphone photo of {topic}, iPhone shot, {setting}, natural daylight, amateur photographer, unedited raw photo, no filters",
                f"Overhead phone snapshot of {topic}, flat lay on scratched surface, casual mobile snapshot",
                f"Quick photo of {topic}, 45-degree angle, slightly blurred background, everyday scene",
                f"Close-up phone camera shot of {topic}, visible grain, natural imperfections, no post-processing"
            ]

