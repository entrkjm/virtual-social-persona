"""
Agent Memory (JSON-based, v1)
상호작용/좋아요/관심사 기록
"""
import json
import os
from datetime import datetime


class AgentMemory:
    def __init__(self, storage_path="agent_memory.json"):
        self.storage_path = storage_path
        self.memory = self._load()

    def _load(self):
        default = {"interactions": [], "facts": {}, "likes": [], "curiosity": {}, "archive": [], "responded_mentions": []}
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key in default:
                    if key not in data:
                        data[key] = default[key]
                return data
            except:
                return default
        return default

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def add_interaction(self, user, post_text, reply_text, tweet_id=None):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user,
            "post": post_text,
            "reply": reply_text,
            "tweet_id": str(tweet_id) if tweet_id else None
        }
        self.memory["interactions"].append(entry)
        # 최대 100개까지만 유지 (간단한 버전)
        if len(self.memory["interactions"]) > 100:
            self.memory["interactions"] = self.memory["interactions"][-100:]
        self._save()

    def add_fact(self, key, value):
        self.memory["facts"][key] = value
        self._save()

    def is_already_replied(self, tweet_id):
        tweet_id_str = str(tweet_id)
        for entry in self.memory["interactions"]:
            if entry.get("tweet_id") == tweet_id_str:
                return True
        return False

    def add_like(self, tweet_id):
        tweet_id_str = str(tweet_id)
        if tweet_id_str not in self.memory["likes"]:
            self.memory["likes"].append(tweet_id_str)
            if len(self.memory["likes"]) > 500: # 좋아요는 좀 더 많이 기억
                self.memory["likes"] = self.memory["likes"][-500:]
            self._save()

    def is_already_liked(self, tweet_id):
        return str(tweet_id) in self.memory["likes"]

    def is_interacted(self, tweet_id):
        return self.is_already_replied(tweet_id) or self.is_already_liked(tweet_id)

    def get_responded_tweet_ids(self):
        """처리 완료한 멘션/답글 ID 목록"""
        if "responded_mentions" not in self.memory:
            self.memory["responded_mentions"] = []
        return set(self.memory["responded_mentions"])

    def mark_tweet_responded(self, tweet_id):
        """멘션/답글 처리 완료 기록"""
        if "responded_mentions" not in self.memory:
            self.memory["responded_mentions"] = []
        tweet_id_str = str(tweet_id)
        if tweet_id_str not in self.memory["responded_mentions"]:
            self.memory["responded_mentions"].append(tweet_id_str)
            if len(self.memory["responded_mentions"]) > 500:
                self.memory["responded_mentions"] = self.memory["responded_mentions"][-500:]
            self._save()

    def get_recent_context(self, limit=5):
        """LLM 프롬프트용 최근 활동 / Recent activity for prompt"""
        recent = self.memory["interactions"][-limit:]
        if not recent:
            return "최근 활동 내역이 없습니다."
        
        context = "### 최근 활동 내역 (Recent Activities):\n"
        for entry in recent:
            context += f"- [{entry['timestamp']}] @{entry['user']}: {entry['reply']}\n"
        return context

    def get_facts_context(self):
        """LLM 프롬프트용 유저 정보 / User facts for prompt"""
        facts = self.memory["facts"]
        if not facts:
            return "아직 학습된 사람 특징이 없습니다."
        
        context = "### 학습된 사용자 정보 (Learned Profiles):\n"
        for k, v in facts.items():
            context += f"- {k}: {v}\n"
        return context

    def track_keyword(self, keyword: str, source: str = "unknown"):
        """Layer 2: 관심사 추적 / Curiosity tracking (확장 구조)"""
        if "curiosity" not in self.memory:
            self.memory["curiosity"] = {}

        keyword = keyword.lower().strip()
        if not keyword or len(keyword) < 2:
            return

        now = datetime.now().isoformat()

        # 기존 데이터 마이그레이션 (숫자 → dict)
        if keyword in self.memory["curiosity"]:
            existing = self.memory["curiosity"][keyword]
            if isinstance(existing, (int, float)):
                self.memory["curiosity"][keyword] = {
                    "count": existing,
                    "first_seen": now,
                    "last_seen": now,
                    "sources": [source]
                }
            else:
                existing["count"] = existing.get("count", 0) + 1
                existing["last_seen"] = now
                if source not in existing.get("sources", []):
                    existing["sources"] = existing.get("sources", [])[-4:] + [source]
        else:
            self.memory["curiosity"][keyword] = {
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                "sources": [source]
            }

        self._save()

    def get_top_interests(self, limit: int = 10) -> list:
        """상위 관심사 목록 (기본 10개로 확장)"""
        if "curiosity" not in self.memory or not self.memory["curiosity"]:
            return []

        def get_count(item):
            k, v = item
            if isinstance(v, (int, float)):
                return v
            return v.get("count", 0)

        sorted_interests = sorted(
            self.memory["curiosity"].items(),
            key=get_count,
            reverse=True
        )
        return [k for k, _ in sorted_interests[:limit]]

    def get_interest_detail(self, keyword: str) -> dict:
        """특정 관심사 상세 정보"""
        keyword = keyword.lower().strip()
        if "curiosity" not in self.memory:
            return {}

        data = self.memory["curiosity"].get(keyword)
        if not data:
            return {}

        if isinstance(data, (int, float)):
            return {"count": data}

        return data

    def decay_curiosity(self, decay_rate: float = 0.7):
        """관심사 감쇠 / Decay old interests"""
        if "curiosity" not in self.memory:
            return

        for keyword in list(self.memory["curiosity"].keys()):
            data = self.memory["curiosity"][keyword]

            if isinstance(data, (int, float)):
                new_count = data * decay_rate
            else:
                new_count = data.get("count", 0) * decay_rate
                data["count"] = new_count

            if new_count < 0.5:
                del self.memory["curiosity"][keyword]
            elif isinstance(data, (int, float)):
                self.memory["curiosity"][keyword] = new_count

        self._save()

    def summarize_old_interactions(self, llm_client=None, threshold=50):
        """오래된 대화 압축 / Compress old interactions"""
        if len(self.memory["interactions"]) < threshold:
            return  # 아직 요약할 필요 없음

        # 오래된 절반을 아카이브로 이동
        to_archive = self.memory["interactions"][:threshold//2]
        self.memory["interactions"] = self.memory["interactions"][threshold//2:]

        if "archive" not in self.memory:
            self.memory["archive"] = []

        # 요약 생성 (LLM 사용)
        if llm_client:
            try:
                summary_prompt = f"""
                다음은 AI 셰프의 과거 대화 기록입니다. 이를 읽고 중요한 사실만 추출하여 한 문장으로 요약하세요.

                대화 기록:
                {to_archive[:10]}  # 샘플만 전달

                출력 형식: "유저명: 특징 요약"
                """
                summary = llm_client.generate(summary_prompt, system_prompt="You are a memory summarizer.")

                # facts에 추가
                self.memory["facts"][f"archived_{datetime.now().strftime('%Y%m%d')}"] = summary
            except Exception as e:
                print(f"[MEMORY] Summarization failed: {e}")

        # 아카이브에 원본 저장 (나중에 삭제 가능)
        self.memory["archive"].extend(to_archive)

        # 아카이브도 일정 크기 이상이면 삭제
        if len(self.memory["archive"]) > 200:
            self.memory["archive"] = self.memory["archive"][-100:]

        self._save()
        print(f"[MEMORY] Summarized {len(to_archive)} interactions")

    def get_interaction_count(self, user: str) -> int:
        """특정 유저와의 상호작용 횟수"""
        user_lower = user.lower().lstrip('@')
        count = 0
        for entry in self.memory["interactions"]:
            entry_user = entry.get("user", "").lower().lstrip('@')
            if entry_user == user_lower:
                count += 1
        return count

# Global instance
agent_memory = AgentMemory()
