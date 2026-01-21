"""
Interaction Intelligence
LLM 기반 트윗 분석/판단 (Perceive + Judge)
Response type 결정 (QUIP/SHORT/NORMAL/LONG)
"""
from core.llm import llm_client
from agent.persona.persona_loader import active_persona
import json
from typing import Dict, List
from agent.platforms.interface import SocialPost
from enum import Enum


class ResponseType(str, Enum):
    QUIP = "quip"      # 1-15자, LLM 없이 패턴 풀에서
    SHORT = "short"    # 15-50자, 간단 프롬프트
    NORMAL = "normal"  # 50-100자, 표준 답글
    LONG = "long"      # 100+자, TMI 모드 (전문 분야 주제)
    PERSONAL = "personal"  # 30-80자, 개인 감상 (전문성 없이)


class InteractionIntelligence:

    @staticmethod
    def perceive_post(post: SocialPost) -> Dict:
        """Perceive: 트윗 의미/감정/의도 분석 + 응답 유형 결정"""
        tweet_text = post.text
        user_handle = post.user.username
        tweet_length = len(tweet_text)
        domain = active_persona.domain
        domain_name = domain.name
        domain_perspective = domain.perspective
        domain_relevance_desc = domain.relevance_desc

        # [PRE-CALCULATION] 1. 언어 필터 (한국어 포함 여부)
        if not InteractionIntelligence._contains_korean(tweet_text):
            return {
                "topics": [],
                "sentiment": "neutral",
                "intent": "foreign_language",
                "relevance_to_domain": 0.0,
                "complexity": "simple",
                "quip_category": "none",
                "user_profile_hint": "외국어 사용자",
                "my_angle": "",
                "tweet_length": tweet_length,
                "response_type": ResponseType.NORMAL,
                "skipped": True,
                "skip_reason": "No Korean text"
            }

        # [PRE-CALCULATION] 2. 스팸 필터 (키워드 기반)
        if InteractionIntelligence._is_spam(tweet_text):
            return {
                "topics": [],
                "sentiment": "negative",
                "intent": "spam",
                "relevance_to_domain": 0.0,
                "complexity": "simple",
                "quip_category": "none",
                "user_profile_hint": "스팸/광고 계정",
                "my_angle": "",
                "tweet_length": tweet_length,
                "response_type": ResponseType.NORMAL,
                "skipped": True,
                "skip_reason": "Spam keywords detected"
            }

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

            # response_type 결정 (config-driven) - social/config.yaml에서 response_strategy 읽기
            social_config = active_persona.platform_configs.get('twitter', {}).get('modes', {}).get('social', {}).get('config', {})
            perception["response_type"] = InteractionIntelligence._determine_response_type(
                perception, social_config
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
            'normal': 0.34,  # Increased
            'long': 0.01,    # Reduced (Professionalism down)
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
    def batch_perceive_tweets(tweets: List[SocialPost]) -> List[Dict]:
        """배치 분석: 여러 트윗을 한 번의 LLM 호출로 분석"""
        results = []
        candidates_for_llm = []
        
        # 1. Pre-filtering (Local)
        for i, post in enumerate(tweets):
            tweet_text = post.text
            tweet_length = len(tweet_text)
            
            # 언어 필터
            if not InteractionIntelligence._contains_korean(tweet_text):
                results.append({
                    "id": post.id,
                    "index": i,
                    "topics": [],
                    "sentiment": "neutral",
                    "intent": "foreign_language",
                    "relevance_to_domain": 0.0,
                    "complexity": "simple",
                    "user_profile_hint": "외국어 사용자",
                    "my_angle": "",
                    "tweet_length": tweet_length,
                    "skipped": True,
                    "skip_reason": "No Korean text"
                })
                continue

            # 스팸 필터
            if InteractionIntelligence._is_spam(tweet_text):
                results.append({
                    "id": post.id,
                    "index": i,
                    "topics": [],
                    "sentiment": "negative",
                    "intent": "spam",
                    "relevance_to_domain": 0.0,
                    "complexity": "simple",
                    "user_profile_hint": "스팸/광고 계정",
                    "my_angle": "",
                    "tweet_length": tweet_length,
                    "skipped": True,
                    "skip_reason": "Spam keywords detected"
                })
                continue
            
            # LLM 후보군 추가
            candidates_for_llm.append((i, post))

        if not candidates_for_llm:
            return sorted(results, key=lambda x: x['index'])

        # 2. Batch Prompting
        domain = active_persona.domain
        candidates_text = "\n\n".join([
            f"[{idx}] 작성자: {post.user.username}\n내용: {post.text}"
            for idx, post in candidates_for_llm
        ])
        
        prompt = f"""
다음 {len(candidates_for_llm)}개의 트윗을 분석하세요. 각 트윗은 [{candidates_for_llm[0][0]}] 같은 인덱스로 구분됩니다.

트윗 목록:
{candidates_text}

출력 포맷:
JSON List 형태로 출력하세요. 각 항목은 다음 필드를 가집니다:
- index: 입력된 트윗의 인덱스 (정수)
- topics: 핵심 주제 키워드 리스트
- sentiment: positive/neutral/negative
- intent: 질문/공유/불만/칭찬/농담/밈/기타
- relevance_to_domain: {domain.relevance_desc} (0.0~1.0)
- complexity: simple/moderate/complex
- user_profile_hint: 유저 특징 추론 (한 문장)
- my_angle: {domain.perspective} 관점의 코멘트 (없으면 빈 문자열)

JSON List만 출력하세요.
"""
        try:
            response = llm_client.generate(prompt, system_prompt="You are a batch tweet analyzer.")
            clean_response = response.replace("```json", "").replace("```", "").strip()
            
            # JSON 파싱 시도 (가끔 마크다운이 섞일 수 있음)
            if '[' not in clean_response:
                raise ValueError("No JSON list found")
            
            # 리스트 부분만 추출
            start = clean_response.find('[')
            end = clean_response.rfind(']') + 1
            json_str = clean_response[start:end]
            
            analyzed_list = json.loads(json_str)
            
            # 결과 매핑
            for item in analyzed_list:
                idx = item.get('index')
                # 원본 포스트 찾기
                original_post = next((p for i, p in candidates_for_llm if i == idx), None)
                if original_post:
                    item['tweet_length'] = len(original_post.text)
                    social_config = active_persona.platform_configs.get('twitter', {}).get('modes', {}).get('social', {}).get('config', {})
                    item['response_type'] = InteractionIntelligence._determine_response_type(
                        item, social_config
                    )
                    results.append(item)

        except Exception as e:
            print(f"[BATCH-PERCEIVE] Error: {e}")
            # 에러 시 남은 후보들 실패 처리
            for i, post in candidates_for_llm:
                results.append({
                    "index": i,
                    "skipped": True,
                    "skip_reason": "Batch Analysis Failed"
                })

        # 인덱스 순 정렬하여 반환 (스키마 맞춤)
        return sorted(results, key=lambda x: x.get('index', 0))

    @staticmethod
    def _contains_korean(text: str) -> bool:
        """한글 포함 여부 확인"""
        import re
        # 한글 유니코드 범위: AC00-D7A3 (가-힣)
        korean_pattern = re.compile(r'[가-힣]')
        return bool(korean_pattern.search(text))

    @staticmethod
    def _is_spam(text: str) -> bool:
        """스팸 키워드 확인"""
        spam_keywords = [
            "crypto", "nft", "airdrop", "giveaway", "follow back", "f4f",
            "promotion", "dm for", "send me", "bitcoin", "eth", "solana",
            "casino", "bet", "jackpot"
        ]
        text_lower = text.lower()
        for kw in spam_keywords:
            if kw in text_lower:
                return True
        return False

# Global instance
interaction_intelligence = InteractionIntelligence()
