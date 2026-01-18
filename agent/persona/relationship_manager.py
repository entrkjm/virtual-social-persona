"""
Relationship Manager
유저 관계 추적 (사전정의 + 동적)
"""
import yaml
import re
from datetime import datetime
from typing import Dict, Optional


class RelationshipManager:
    def __init__(self, persona_name: str, memory_instance):
        self.persona_name = persona_name
        self.memory = memory_instance
        self.predefined_relationships = self._load_relationships()

    def _load_relationships(self) -> Dict:
        try:
            path = f"personas/{self.persona_name}/relationships.yaml"
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {"relationships": {}}

    def get_predefined_relationship(self, twitter_handle: str) -> Optional[Dict]:
        relationships = self.predefined_relationships.get("relationships", {})
        
        # 모든 카테고리 검색
        for category, people in relationships.items():
            for person in people:
                handle_pattern = person.get("twitter_handle", "")
                
                # 정규식 매칭
                if re.match(handle_pattern, twitter_handle):
                    # condition 체크 (있으면)
                    condition = person.get("condition", "default")
                    if condition == "default" or self._check_condition(twitter_handle, condition):
                        return {
                            "category": category,
                            "name": person.get("name"),
                            "relationship": person.get("relationship"),
                            "interaction_style": person.get("interaction_style"),
                            "topics": person.get("topics", [])
                        }
        
        return None

    def _check_condition(self, twitter_handle: str, condition: str) -> bool:
        try:
            # 메모리에서 유저 정보 가져오기
            user_data = self.memory.memory.get("relationships", {}).get(twitter_handle, {})
            interaction_count = user_data.get("interaction_count", 0)
            sentiment = user_data.get("sentiment", "neutral")
            
            # 조건 평가
            return eval(condition, {"interaction_count": interaction_count, "sentiment": sentiment})
        except:
            return False

    def get_dynamic_relationship(self, twitter_handle: str) -> Optional[Dict]:
        return self.memory.memory.get("relationships", {}).get(twitter_handle)

    def get_relationship_context(self, twitter_handle: str) -> str:
        """LLM 프롬프트용 관계 정보 / Relationship context for prompt"""
        predefined = self.get_predefined_relationship(twitter_handle)
        dynamic = self.get_dynamic_relationship(twitter_handle)
        context = f"### {twitter_handle}:\n"
        
        if predefined:
            context += f"- 관계: {predefined['relationship']}\n"
            context += f"- 소통 스타일: {predefined['interaction_style']}\n"
            if predefined['topics']:
                context += f"- 주요 주제: {', '.join(predefined['topics'])}\n"
        
        if dynamic:
            context += f"- 첫 만남: {dynamic.get('first_met', '알 수 없음')}\n"
            context += f"- 상호작용 횟수: {dynamic.get('interaction_count', 0)}회\n"
            context += f"- 감정: {dynamic.get('sentiment', 'neutral')}\n"
            if dynamic.get('topics_discussed'):
                context += f"- 과거 대화 주제: {', '.join(dynamic['topics_discussed'][:3])}\n"
            if dynamic.get('notes'):
                context += f"- 메모: {dynamic['notes']}\n"
        
        if not predefined and not dynamic:
            context += "- 초면\n"

        return context

    def update_relationship(self, twitter_handle: str, interaction_data: Dict):
        if "relationships" not in self.memory.memory:
            self.memory.memory["relationships"] = {}
        
        user_data = self.memory.memory["relationships"].get(twitter_handle, {
            "first_met": datetime.now().strftime("%Y-%m-%d"),
            "interaction_count": 0,
            "sentiment": "neutral",
            "topics_discussed": [],
            "notes": ""
        })

        user_data["interaction_count"] += 1
        user_data["sentiment"] = interaction_data.get("sentiment", user_data["sentiment"])

        new_topics = interaction_data.get("topics", [])
        user_data["topics_discussed"] = list(set(user_data["topics_discussed"] + new_topics))[:10]

        if interaction_data.get("notes"):
            user_data["notes"] = interaction_data["notes"]
        
        self.memory.memory["relationships"][twitter_handle] = user_data
        self.memory._save()


relationship_manager = None


def initialize_relationship_manager(persona_name: str, memory_instance):
    global relationship_manager
    relationship_manager = RelationshipManager(persona_name, memory_instance)
    return relationship_manager
