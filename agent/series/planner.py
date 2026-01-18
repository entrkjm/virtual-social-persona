"""
Series Planner
기획 담당: 토픽 선정 및 방향성 수립 + Curator (자율 수급)
"""
import random
import json
from typing import List, Optional, Dict, Any
from agent.series.archiver import SeriesArchiver
from core.llm import llm_client

class SeriesPlanner:
    def __init__(self, persona_id: str):
        self.archiver = SeriesArchiver(persona_id)

    def plan_next_episode(self, platform: str, series_config: Dict) -> Optional[Dict[str, Any]]:
        """
        다음 에피소드 기획 (Queue 기반)
        """
        series_id = series_config['id']
        curation_config = series_config.get('curation', {})
        
        # 1. 큐 확인 및 보충 (Curator)
        if curation_config.get('enabled'):
            self._ensure_queue(platform, series_id, curation_config)
            
            # 큐에서 하나 꺼내기
            item = self.archiver.pop_from_queue(platform, series_id)
            if item:
                return {
                    "topic": item['topic'],
                    "series_id": series_id,
                    "platform": platform,
                    "angle": "Curated Topic" # 기획 의도
                }
        
        # 2. Fallback: 기존 정적 리스트 (topics) 또는 큐가 비었을 때
        # (YAML에서 topics가 삭제되었으므로 큐가 비면 실패함)
        return None

    def _ensure_queue(self, platform: str, series_id: str, curation_config: Dict):
        """큐가 부족하면 채워넣음"""
        queue = self.archiver.get_queue(platform, series_id)
        if len(queue) >= 3:
            return

        print(f"[SeriesPlanner] Queue low ({len(queue)}), curating new topics for {series_id}...")
        
        # 이력 로드 (중복 방지용)
        history = self.archiver.load_history(platform)
        used_topics = history.get("series_usage", {}).get(series_id, {}).get("used_topics", [])
        
        # LLM으로 새 토픽 발굴
        new_items = self._curate_topics(curation_config, used_topics + [q['topic'] for q in queue])
        
        if new_items:
            self.archiver.add_to_queue(platform, series_id, new_items)
            print(f"[SeriesPlanner] Added {len(new_items)} topics to queue: {[i['topic'] for i in new_items]}")

    def _curate_topics(self, config: Dict, exclude_topics: List[str]) -> List[Dict]:
        """LLM을 이용해 토픽 추천 받기"""
        prompt_text = config.get('prompt', '')
        count = config.get('count_per_fetch', 5)
        
        system_prompt = "You are a creative content curator. Output ONLY valid JSON array."
        user_prompt = f"""
{prompt_text}

[Constraints]
1. Recommend {count} unique topics.
2. EXCLUDE these topics (already used): {', '.join(exclude_topics[:20])}...
3. Output format must be a JSON array of objects:
[
  {{"topic": "Name of the dish/topic", "reason": "Why this is interesting"}},
  ...
]
4. Do not include markdown formatting like ```json. Just raw JSON.
"""
        try:
            response = llm_client.generate(user_prompt, system_prompt)
            # JSON 파싱 (간단한 정제 포함)
            cleaned = response.strip().replace("```json", "").replace("```", "")
            items = json.loads(cleaned)
            
            # 포맷 검증
            valid_items = []
            for item in items:
                if 'topic' in item:
                    valid_items.append(item)
            return valid_items
            
        except Exception as e:
            print(f"[SeriesPlanner] Curation failed: {e}")
            return []

    def get_last_used_at(self, platform: str, series_config: Dict) -> Optional[str]:
        return self.archiver.get_last_used_at(platform, series_config['id'])
