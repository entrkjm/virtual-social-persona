"""
Series Archiver
데이터 저장 및 자산 관리
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from config.settings import settings

class SeriesArchiver:
    def __init__(self, persona_id: str):
        self.persona_id = persona_id
        # Persona-centric structure: data/personas/{persona_id}/series
        self.base_dir = os.path.join(settings.DATA_DIR, "personas", persona_id, "series")
        self.assets_dir = os.path.join(self.base_dir, "assets")
        self.db_dir = os.path.join(self.base_dir, "db")
        
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.db_dir, exist_ok=True)

    def prepare_asset_dir(self, series_id: str, topic_slug: str) -> str:
        """
        자산 저장소 준비
        data/series/chef_choi/assets/{series_id}/{date}_{topic}/
        """
        date_str = datetime.now().strftime("%Y%m%d")
        # slugify topic (simple version)
        safe_topic = "".join(c if c.isalnum() else "_" for c in topic_slug)[:20]
        dir_name = f"{date_str}_{safe_topic}"
        
        path = os.path.join(self.assets_dir, series_id, dir_name)
        os.makedirs(path, exist_ok=True)
        return path

    def save_asset(self, series_id: str, topic: str, name: str, data: bytes) -> str:
        """자산 파일 저장"""
        dir_path = self.prepare_asset_dir(series_id, topic)
        file_path = os.path.join(dir_path, name)
        with open(file_path, 'wb') as f:
            f.write(data)
        return file_path

    def log_episode(self, platform: str, series_id: str, data: Dict[str, Any]):
        """
        상세 로그 저장 (JSONL)
        """
        log_file = os.path.join(self.db_dir, f"{platform}_log.jsonl")
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "series_id": series_id,
            "data": data
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_history(self, platform: str) -> Dict[str, Any]:
        """간략 이력 로드 (Planner용)"""
        path = os.path.join(self.db_dir, f"{platform}_history.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"series_usage": {}}

    def update_history(self, platform: str, series_id: str, topic: str):
        """간략 이력 업데이트"""
        path = os.path.join(self.db_dir, f"{platform}_history.json")
        history = self.load_history(platform)
        
        if "series_usage" not in history:
            history["series_usage"] = {}
            
        usage = history["series_usage"].setdefault(series_id, {"used_topics": [], "last_used_at": ""})
        
        if topic not in usage["used_topics"]:
            usage["used_topics"].append(topic)
        usage["last_used_at"] = datetime.now().isoformat()
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
    def get_last_used_at(self, platform: str, series_id: str) -> Optional[str]:
         history = self.load_history(platform)
         return history.get("series_usage", {}).get(series_id, {}).get("last_used_at")

    # --- Queue Management ---

    def _get_queue_path(self, platform: str, series_id: str) -> str:
        return os.path.join(self.db_dir, f"{platform}_{series_id}_queue.json")

    def get_queue(self, platform: str, series_id: str) -> List[Dict]:
        path = self._get_queue_path(platform, series_id)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def save_queue(self, platform: str, series_id: str, queue: List[Dict]):
        path = self._get_queue_path(platform, series_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)

    def add_to_queue(self, platform: str, series_id: str, items: List[Dict]):
        """큐에 아이템 추가"""
        queue = self.get_queue(platform, series_id)
        
        # 중복 제거 (topic 기준)
        existing_topics = {item['topic'] for item in queue}
        for item in items:
            if item['topic'] not in existing_topics:
                queue.append(item)
                
        self.save_queue(platform, series_id, queue)

    def pop_from_queue(self, platform: str, series_id: str) -> Optional[Dict]:
        """큐에서 아이템 하나 꺼내기 (FIFO)"""
        queue = self.get_queue(platform, series_id)
        if not queue:
            return None
            
        item = queue.pop(0) # FIFO
        self.save_queue(platform, series_id, queue)
        return item
