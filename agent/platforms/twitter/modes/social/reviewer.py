"""
Social Reply Reviewer
답글 품질 검토 및 정제 (LLM 기반)
"""
import json
from typing import Dict, Tuple

from core.llm import llm_client
from config.settings import settings

class SocialReplyReviewer:
    def __init__(self, persona):
        self.persona = persona

    def review_reply(self, target_text: str, draft_reply: str) -> str:
        """
        답글 초안을 검토하고 필요시 수정본 반환
        Returns:
            refined_reply (str)
        """
        # 검토 스킵 조건 (너무 짧거나 비어있음)
        if not draft_reply or len(draft_reply) < 5:
            return draft_reply

        prompt = f"""
당신은 소셜 미디어 커뮤니케이션 전문가이자 [{self.persona.name}] 페르소나 관리자입니다.
다음 답글 초안을 검토하고, 문제가 있다면 수정하세요.

[상황]
- 상대방 글: "{target_text}"
- 초안 답글: "{draft_reply}"

[검토 기준 (Critique Criteria)]
1. **언어**: 무조건 한국어인가? (영어 절대 금지). 영어로 되어있다면 한국어로 번역/수정.
2. **말투**: "{self.persona.name}" 특유의 말투가 잘 드러나는가? 
   - 예: "~거든요", "~인 거죠", "이게 참... 재미있는 게" 등 (설정이 있다면)
   - 너무 딱딱하거나 기계적이지 않은가?
3. **길이**: 불필요하게 길지 않은가? (TMI 모드가 아니면 간결하게)
4. **적절성**: 상대방 글에 대한 반응으로 자연스러운가?
5. **금지**: 자기소개("저는 AI입니다"), 해시태그 남발, 문맥 없는 헛소리.

[지시]
위 기준으로 초안을 평가하세요.
- 완벽하다면 초안을 그대로 유지하세요.
- 문제가 있다면 자연스럽고 매력적인 한국어로 수정하세요.

[출력 형식 (JSON Only)]
{{
    "is_good": true/false,
    "issue": "문제점 요약 (없으면 빈칸)",
    "refined_text": "수정된 텍스트 (완벽하면 초안 유지)"
}}
"""
        try:
            response = llm_client.generate(prompt)
            clean_res = response.strip()
            if clean_res.startswith('```'):
                clean_res = clean_res.split('```')[1]
                if clean_res.startswith('json'):
                    clean_res = clean_res[4:]
            
            data = json.loads(clean_res)
            
            refined = data.get('refined_text', draft_reply)
            
            # 만약 수정된 텍스트가 영어라면(혹시나), 원본을 반환하거나 다시 시도해야 하지만
            # 여기서는 Reviewer를 믿고 반환. (추후 언어 감지 로직 추가 가능)
            
            if not data.get('is_good'):
                print(f"[Reviewer] Refined reply: '{draft_reply}' -> '{refined}' ({data.get('issue')})")
            
            return refined

        except Exception as e:
            print(f"[SocialReplyReviewer] Review failed: {e}")
            return draft_reply
