"""
Interaction Intelligence
LLM 기반 트윗 분석/판단 (Perceive + Judge)
Response type 결정 (QUIP/SHORT/NORMAL/LONG)
"""
from core.llm import llm_client
from agent.persona.persona_loader import active_persona
import json
from typing import Dict, List
from enum import Enum


class ResponseType(str, Enum):
    QUIP = "quip"      # 1-15자, LLM 없이 패턴 풀에서
    SHORT = "short"    # 15-50자, 간단 프롬프트
    NORMAL = "normal"  # 50-100자, 표준 답글
    LONG = "long"      # 100+자, TMI 모드 (전문 분야 주제)
    PERSONAL = "personal"  # 30-80자, 개인 감상 (전문성 없이)


class InteractionIntelligence:

    @staticmethod
    def perceive_tweet(tweet_text: str, user_handle: str) -> Dict:
        """Perceive: 트윗 의미/감정/의도 분석 + 응답 유형 결정"""
        tweet_length = len(tweet_text)
        domain = active_persona.domain
        domain_name = domain.name
        domain_perspective = domain.perspective
        domain_relevance_desc = domain.relevance_desc

        perception_prompt = f"""
다음 트윗을 분석하세요:

작성자: {user_handle}
내용: {tweet_text}

JSON 형식으로 출력 (다른 설명 없이 JSON만):
{{
    "topics": ["핵심 주제 키워드 1~3개"],
    "sentiment": "positive 또는 neutral 또는 negative",
    "intent": "질문 또는 공유 또는 불만 또는 칭찬 또는 농담 또는 밈 또는 기타",
    "relevance_to_domain": 0.0에서 1.0 사이 숫자,
    "complexity": "simple 또는 moderate 또는 complex",
    "quip_category": "agreement 또는 impressed 또는 casual 또는 food_related 또는 skeptical 또는 simple_answer 또는 none",
    "user_profile_hint": "이 사람의 특징이나 관심사 추론 (한 문장)",
    "my_angle": "{domain_perspective} 이 트윗에 대해 할 수 있는 말이나 생각 (한 문장, 없으면 빈 문자열)"
}}

relevance_to_domain: {domain_relevance_desc} (0.0 = 전혀 무관, 1.0 = 완전 관련)

complexity 판단 기준:
- simple: 밈, 단순 감탄, 짧은 의견, 농담 (짧은 반응이 자연스러움)
- moderate: 일반적인 대화, 간단한 질문/공유
- complex: 깊은 질문, 전문 주제, {domain_name} 관련 논의 (긴 답변이 적절함)

quip_category: 짧은 반응(1-15자)으로 충분한 경우 해당 카테고리 선택, 아니면 none
"""

        try:
            response = llm_client.generate(perception_prompt, system_prompt="You are a tweet analyzer.")
            clean_response = response.replace("```json", "").replace("```", "").strip()
            perception = json.loads(clean_response)
            perception["tweet_length"] = tweet_length

            # response_type 결정 (config-driven)
            perception["response_type"] = InteractionIntelligence._determine_response_type(
                perception, active_persona.behavior
            )

            return perception
        except Exception as e:
            print(f"[PERCEIVE] {e}")
            return {
                "topics": [],
                "sentiment": "neutral",
                "intent": "기타",
                "relevance_to_domain": 0.0,
                "complexity": "moderate",
                "quip_category": "none",
                "user_profile_hint": "분석 실패",
                "my_angle": "",
                "tweet_length": tweet_length,
                "response_type": ResponseType.NORMAL
            }

    @staticmethod
    def _determine_response_type(perception: Dict, behavior_config: Dict) -> ResponseType:
        """Config-driven response type selection"""
        import random
        
        strategy = behavior_config.get('response_strategy', {})
        
        # Get base probabilities
        base_probs = strategy.get('base_probabilities', {
            'quip': 0.20,
            'short': 0.40,
            'normal': 0.30,
            'long': 0.05,
            'personal': 0.05
        })
        
        # Start with base probabilities
        probs = dict(base_probs)
        
        # Apply tweet length modifiers
        tweet_len = perception.get('tweet_length', 50)
        length_mods = strategy.get('tweet_length_modifiers', {})
        
        if tweet_len <= length_mods.get('short_tweet', {}).get('threshold', 30):
            mod_probs = length_mods.get('short_tweet', {}).get('probabilities', {})
            probs.update(mod_probs)
        elif tweet_len <= length_mods.get('medium_tweet', {}).get('threshold', 80):
            mod_probs = length_mods.get('medium_tweet', {}).get('probabilities', {})
            probs.update(mod_probs)
        else:
            mod_probs = length_mods.get('long_tweet', {}).get('probabilities', {})
            probs.update(mod_probs)
        
        # Apply domain relevance modifiers
        domain_rel = perception.get('relevance_to_domain', 0.0)
        domain_mods = strategy.get('domain_modifiers', {})
        
        if domain_rel >= 0.7:
            # High relevance
            high_rel = domain_mods.get('high_relevance', {})
            probs['long'] = max(0, probs.get('long', 0) + high_rel.get('long_boost', 0))
            probs['personal'] = max(0, probs.get('personal', 0) + high_rel.get('personal_boost', 0))
        elif domain_rel < 0.3:
            # Low relevance
            low_rel = domain_mods.get('low_relevance', {})
            probs['long'] = max(0, probs.get('long', 0) + low_rel.get('long_penalty', 0))
            probs['personal'] = max(0, probs.get('personal', 0) + low_rel.get('personal_boost', 0))
        
        # Normalize probabilities
        total = sum(probs.values())
        if total > 0:
            probs = {k: v/total for k, v in probs.items()}
        
        # Weighted random selection
        types = [ResponseType.QUIP, ResponseType.SHORT, ResponseType.NORMAL, ResponseType.LONG, ResponseType.PERSONAL]
        weights = [probs.get(t.value, 0) for t in types]
        
        return random.choices(types, weights=weights)[0]

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
        domain_relevance_desc = active_persona.domain.relevance_desc
        judgment_prompt = f"""
### 상황 분석:
- 트윗 작성자: {tweet['user']}
- 트윗 내용: {tweet['text']}

### AI 분석 결과:
- 주제: {', '.join(perception['topics'])}
- 감정: {perception['sentiment']}
- 의도: {perception['intent']}
- {domain_relevance_desc}: {perception['relevance_to_domain']}
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
