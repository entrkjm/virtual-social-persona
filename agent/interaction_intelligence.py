"""
Interaction Intelligence
LLM 기반 트윗 분석/판단 (Perceive + Judge)
"""
from core.llm import llm_client
import json
from typing import Dict, List


class InteractionIntelligence:

    @staticmethod
    def perceive_tweet(tweet_text: str, user_handle: str) -> Dict:
        """Perceive: 트윗 의미/감정/의도 분석"""
        perception_prompt = f"""
다음 트윗을 분석하세요:

작성자: {user_handle}
내용: {tweet_text}

JSON 형식으로 출력 (다른 설명 없이 JSON만):
{{
    "topics": ["핵심 주제 키워드 1~3개"],
    "sentiment": "positive 또는 neutral 또는 negative",
    "intent": "질문 또는 공유 또는 불만 또는 칭찬 또는 기타",
    "relevance_to_cooking": 0.0에서 1.0 사이 숫자,
    "user_profile_hint": "이 사람의 특징이나 관심사 추론 (한 문장)",
    "my_angle": "요리사 관점에서 이 트윗에 대해 할 수 있는 말이나 생각 (한 문장, 없으면 빈 문자열)"
}}
"""
        
        try:
            response = llm_client.generate(perception_prompt, system_prompt="You are a tweet analyzer.")
            # JSON 파싱
            clean_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_response)
        except Exception as e:
            print(f"[PERCEIVE] {e}")
            return {
                "topics": [],
                "sentiment": "neutral",
                "intent": "기타",
                "relevance_to_cooking": 0.0,
                "user_profile_hint": "분석 실패",
                "my_angle": ""
            }

    @staticmethod
    def judge_with_context(
        tweet: Dict,
        perception: Dict,
        relationship_context: str,
        current_mood: str,
        curiosity: List[str],
        system_prompt: str
    ) -> Dict:
        """Judge: 맥락 기반 행동 결정"""
        judgment_prompt = f"""
### 상황 분석:
- 트윗 작성자: {tweet['user']}
- 트윗 내용: {tweet['text']}

### AI 분석 결과:
- 주제: {', '.join(perception['topics'])}
- 감정: {perception['sentiment']}
- 의도: {perception['intent']}
- 요리 관련도: {perception['relevance_to_cooking']}
- 유저 특징: {perception['user_profile_hint']}

{relationship_context}

### 당신의 현재 상태:
- 기분: {current_mood}
- 최근 관심사: {', '.join(curiosity) if curiosity else '없음'}

### 행동 선택:
다음 중 하나를 선택하세요:
1. IGNORE: 무시하고 넘어감
2. LIKE: 좋아요만 누름 (말은 안 함)
3. REPLY: 답글 작성
4. LIKE_REPLY: 좋아요 + 답글
5. REMEMBER: 기억만 하고 행동은 안 함

JSON 형식으로 출력 (다른 설명 없이 JSON만):
{{
    "action": "선택한 행동",
    "reason": "왜 이 행동을 선택했는지 (한 문장)",
    "content": "답글 내용 (REPLY 또는 LIKE_REPLY인 경우, 최대 70자)",
    "memory_update": "이 사람에 대해 기억할 점 (한 문장)"
}}
"""
        
        try:
            response = llm_client.generate(judgment_prompt, system_prompt=system_prompt)
            clean_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_response)
        except Exception as e:
            print(f"[JUDGE] {e}")
            return {
                "action": "IGNORE",
                "reason": "판단 실패",
                "content": None,
                "memory_update": None
            }

    @staticmethod
    def batch_perceive_tweets(tweets: List[Dict]) -> List[Dict]:
        """배치 분석 (현재는 개별 호출) / Batch perceive"""
        results = []
        for tweet in tweets:
            perception = InteractionIntelligence.perceive_tweet(tweet['text'], tweet['user'])
            results.append(perception)
        return results

# Global instance
interaction_intelligence = InteractionIntelligence()
