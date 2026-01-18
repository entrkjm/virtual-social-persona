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
        """LLM을 사용하여 4개의 각기 다른 연출 프롬프트 생성"""
        from core.llm import llm_client
        import json

        guide_json = json.dumps(prompt_guide, indent=2, ensure_ascii=False)
        
        prompt = f"""
You are an expert Food Photographer & Art Director.
Generate 4 DISTINCT prompt variations for the main subject: "{topic}".
Current Situation: {context_str}

Reference the following Guide strictly to build "Photorealistic" prompts:
{guide_json}

REQUIREMENTS:
1. Create 4 different concepts (e.g., Candid, Cinematic/Dark, Macro/Detail, Overhead).
2. Incorporate the "Dynamic State" and "Imperfections" keywords naturally.
3. OUTPUT FORMAT: valid JSON list of strings only. No other text.

Example Output:
[
  "Candid shot of steaming hot Kimchi Stew, 45-degree angle, natural window light...",
  "Overhead view of Kimchi Stew ingredients, messy table, flour dusting...",
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
            # Fallback
            return [f"Professional photo of {topic}, realistic food photography, 8k" for _ in range(4)]
