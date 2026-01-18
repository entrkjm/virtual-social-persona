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
