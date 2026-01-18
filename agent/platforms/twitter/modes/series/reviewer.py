"""
Series Reviewer
텍스트 정제 및 이미지 선정 (Integrated Review)
"""
from typing import List, Dict, Tuple, Any
from core.llm import llm_client
from config.settings import settings
import json

class SeriesReviewer:
    def __init__(self):
        pass

    def review_content(self, draft_text: str, image_prompts: List[str], criteria: str) -> Tuple[str, int, Dict]:
        """
        Draft Text와 4개의 이미지 프롬프트를 보고,
        1. 텍스트 정제 (AI 티 나는 부분 제거)
        2. 최적의 이미지 선택 (프롬프트 기준)
        
        Returns:
            (refined_text, selected_image_index, critique_metadata)
        """
        
        prompts_text = "\n".join([f"{i}. {p}" for i, p in enumerate(image_prompts)])
        
        prompt = f"""
You are a Series Editor & Art Director.
Your task is to finalize the content for publication.

[Draft Text]:
{draft_text}

[Candidate Image Prompts] (Images were generated from these):
{prompts_text}

[Review Criteria]:
{criteria}

INSTRUCTIONS:
1. **Text Refinement**: 
   - Remove any AI artifacts (e.g., emojis if excessive, "**Bold**" markdown, "Here is the tweet", etc.).
   - Make it sound natural and professional (Chef's tone).
   - Keep the original meaning but polish the delivery.

2. **Image Selection**:
   - Choose the ONE image prompt index (0-3) that best matches the refined text's mood.

OUTPUT FORMAT (JSON ONLY):
{{
    "refined_text": "...",
    "selected_index": 0,
    "reason": "..."
}}
"""
        try:
            response = llm_client.generate(prompt, model=settings.GEMINI_PRO_MODEL)
            clean_res = response.strip()
            if clean_res.startswith('```'):
                clean_res = clean_res.split('```')[1]
            if clean_res.startswith('json'):
                clean_res = clean_res[4:]
            
            data = json.loads(clean_res)
            return data.get('refined_text', draft_text), data.get('selected_index', 0), data
            
        except Exception as e:
            print(f"[SeriesReviewer] Review failed: {e}")
            return draft_text, 0, {"error": str(e)}
