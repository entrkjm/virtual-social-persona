"""
Image Critic (Gemini Vision)
이미지 평가 및 선별
"""
import json
import re
from typing import List, Dict, Any
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part, Image
except ImportError:
    vertexai = None
    GenerativeModel = None

from config.settings import settings

class ImageCritic:
    def __init__(self):
        self.model = None
        if settings.USE_VERTEX_AI and vertexai:
            try:
                self.model = GenerativeModel(settings.GEMINI_VISION_MODEL)
                print(f"[ImageCritic] Loaded model: {settings.GEMINI_VISION_MODEL}")
            except Exception as e:
                print(f"[ImageCritic] Init failed: {e}")

    def evaluate(self, images_data: List[bytes], topic: str, criteria: str) -> Dict[str, Any]:
        """
        후보 이미지 중 Best Cut 선정
        Returns: {"selected_index": 0, "reason": "..."}
        """
        if not self.model or not images_data:
            return {"selected_index": 0, "reason": "Default selection (Critic disabled)"}

        print(f"[ImageCritic] Evaluating {len(images_data)} images for '{topic}'...")

        prompt = f"""
You are an expert Art Director and Food Photographer.
I will show you {len(images_data)} candidate images generated for the topic: "{topic}".

[Criteria]
{criteria}

Task:
1. Analyze each image's composition, lighting, and appetizing appeal.
2. Select the ONE best image that perfectly matches the criteria.
3. Reject images with AI artifacts (weird text, distorted objects) if possible.

Output format:
JSON object with keys:
- "selected_index": (integer, 0 to {len(images_data)-1})
- "reason": (string, short explanation)
"""
        # Construct multimodal input
        contents = [prompt]
        for i, data in enumerate(images_data):
            # Image.from_bytes(data) returns an Image object which behaves like a Part
            contents.append(f"\n[Image {i}]")
            contents.append(Image.from_bytes(data))

        try:
            response = self.model.generate_content(contents)
            text = response.text
            
            # JSON clean up
            cleaned = text.strip().replace("```json", "").replace("```", "")
            # Find JSON-like structure if needed
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(0)
                
            result = json.loads(cleaned)
            
            # Validate index
            idx = result.get('selected_index', 0)
            if not isinstance(idx, int) or idx < 0 or idx >= len(images_data):
                result['selected_index'] = 0
                
            return result

        except Exception as e:
            print(f"[ImageCritic] Evaluation failed: {e}")
            return {"selected_index": 0, "reason": f"Error: {e}"}
