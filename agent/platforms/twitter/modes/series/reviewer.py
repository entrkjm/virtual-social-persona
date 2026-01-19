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
당신은 시리즈 에디터이자 아트 디렉터입니다.
출판을 위한 콘텐츠를 최종 검토합니다.

[중요: 반드시 한국어로 응답하세요. 영어 사용 금지]

[초안 텍스트]:
{draft_text}

[후보 이미지 프롬프트] (이 프롬프트로 이미지가 생성됨):
{prompts_text}

[검토 기준]:
{criteria}

지시사항:
1. **텍스트 정제**: 
   - AI 티 나는 부분 제거 (과도한 이모지, "**굵게**" 마크다운, "안녕하세요" 자기소개 등)
   - 자연스럽고 전문적인 셰프 톤으로 수정
   - 원래 의미는 유지하되 전달력을 높일 것
   - 반드시 한국어로 작성. 영어 번역 금지!

2. **이미지 선택**:
   - 정제된 텍스트의 분위기에 가장 잘 맞는 이미지 프롬프트 인덱스(0-3) 선택

출력 형식 (JSON만):
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
