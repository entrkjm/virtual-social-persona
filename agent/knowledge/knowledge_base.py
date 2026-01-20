"""
Knowledge Base
트렌드/키워드 컨텍스트 학습 및 저장
Learn and store context for trends/keywords
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config.settings import settings
from core.llm import llm_client
from agent.platforms.twitter.api.social import search_tweets
from agent.persona.persona_loader import active_persona


KNOWLEDGE_FILE = os.path.join(settings.DATA_DIR, "knowledge_base.json")


class KnowledgeBase:
    def __init__(self):
        self.knowledge: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(KNOWLEDGE_FILE):
            try:
                with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
                    self.knowledge = json.load(f)
                self._cleanup_expired()
            except Exception as e:
                print(f"[KNOWLEDGE] Load failed: {e}")
                self.knowledge = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(KNOWLEDGE_FILE), exist_ok=True)
            with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[KNOWLEDGE] Save failed: {e}")

    def _cleanup_expired(self):
        """만료된 지식 정리"""
        now = datetime.now().isoformat()
        expired = [k for k, v in self.knowledge.items() if v.get('expires_at', '') < now]
        for k in expired:
            del self.knowledge[k]
        if expired:
            self._save()

    def learn_topic(self, keyword: str, force: bool = False, source_platform: str = 'twitter', source_data: List[Dict] = None) -> Optional[Dict]:
        """키워드 조사 후 지식 저장
        
        Args:
            keyword: 학습할 키워드
            force: 기존 지식 덮어쓰기 여부
            source_platform: 출처 플랫폼
            source_data: 외부에서 주입된 데이터 (없으면 Twitter에서 직접 조회)
        """
        if not keyword or len(keyword) < 2:
            return None

        # 이미 학습했고 만료 안 됐으면 스킵
        if keyword in self.knowledge and not force:
            existing = self.knowledge[keyword]
            if existing.get('expires_at', '') > datetime.now().isoformat():
                return existing

        try:
            # 1. 데이터가 주입되지 않았으면 Twitter에서 조회 (레거시 호환)
            # Fallback to Twitter Search (Mock or Real)
            try:
                from agent.platforms.twitter.api.social import search_tweets
                results = search_tweets(keyword, count=3)
                if results:
                    tweets = results
                else:
                    tweets = source_data # Fallback to source_data if search_tweets returns nothing
            except ImportError:
                # If the specific import fails, use source_data
                tweets = source_data
            
            if not tweets:
                return self._create_minimal_knowledge(keyword, source_platform)

            tweets_text = "\n".join([
                f"- @{t.get('user', 'unknown')}: {t.get('text', '')[:100]}"
                for t in tweets[:5]
            ])

            # 2. LLM: 이게 뭔지 요약
            summary_prompt = f"""
다음 트윗들을 보고 '{keyword}'가 왜 화제인지 한 문장으로 요약해줘.
모르겠으면 "알 수 없음"이라고 해.

트윗들:
{tweets_text}

요약 (한 문장):"""

            summary = llm_client.generate(summary_prompt).strip()
            if len(summary) > 200:
                summary = summary[:200]

            # 3. LLM: 내 페르소나 관점에서 관련도/각도
            persona_identity = active_persona.identity if hasattr(active_persona, 'identity') else ""
            core_keywords = active_persona.core_keywords if hasattr(active_persona, 'core_keywords') else []

            relevance_prompt = f"""
나는 "{persona_identity}".
내 관심사: {', '.join(core_keywords)}

'{keyword}'에 대해 ({summary}):
1. 내 관심사와 관련도를 0.0~1.0 사이 숫자로 (0.0=전혀무관, 1.0=완전관련)
2. 내 관점에서 할 말이 있다면 한 문장으로

JSON 형식으로 답해:
{{"relevance": 0.0, "my_angle": "..."}}
"""
            try:
                relevance_raw = llm_client.generate(relevance_prompt).strip()
                # JSON 파싱 시도
                if '{' in relevance_raw:
                    json_str = relevance_raw[relevance_raw.find('{'):relevance_raw.rfind('}')+1]
                    relevance_data = json.loads(json_str)
                else:
                    relevance_data = {"relevance": 0.1, "my_angle": ""}
            except:
                relevance_data = {"relevance": 0.1, "my_angle": ""}

            # 4. 저장
            knowledge = {
                "keyword": keyword,
                "summary": summary,
                "my_angle": relevance_data.get("my_angle", ""),
                "relevance": min(1.0, max(0.0, float(relevance_data.get("relevance", 0.1)))),
                "source_platform": source_platform,
                "source_ids": [t.get('id', '') for t in tweets[:3]],
                "learned_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
            }

            self.knowledge[keyword] = knowledge
            self._save()

            print(f"[KNOWLEDGE] Learned '{keyword}' from {source_platform} (relevance: {knowledge['relevance']:.2f})")
            return knowledge

        except Exception as e:
            print(f"[KNOWLEDGE] Learn failed for '{keyword}': {e}")
            return self._create_minimal_knowledge(keyword, source_platform)

    def _create_minimal_knowledge(self, keyword: str, source_platform: str = 'unknown') -> Dict:
        """최소 지식 (검색 실패 시)"""
        knowledge = {
            "keyword": keyword,
            "summary": "",
            "my_angle": "",
            "relevance": 0.0,
            "source_platform": source_platform,
            "source_ids": [],
            "learned_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=6)).isoformat()  # 짧은 만료
        }
        self.knowledge[keyword] = knowledge
        self._save()
        return knowledge

    def get(self, keyword: str) -> Optional[Dict]:
        """지식 조회"""
        if keyword not in self.knowledge:
            return None

        knowledge = self.knowledge[keyword]
        if knowledge.get('expires_at', '') < datetime.now().isoformat():
            del self.knowledge[keyword]
            self._save()
            return None

        return knowledge

    def get_relevant_topics(self, min_relevance: float = 0.0, limit: int = 10) -> List[str]:
        """관련도 기준 토픽 목록"""
        self._cleanup_expired()

        relevant = [
            (k, v['relevance'])
            for k, v in self.knowledge.items()
            if v.get('relevance', 0) >= min_relevance
        ]
        relevant.sort(key=lambda x: x[1], reverse=True)

        return [k for k, _ in relevant[:limit]]

    def get_for_posting(self, limit: int = 5) -> List[Dict]:
        """포스팅용 토픽 (관련도 + 각도 있는 것)"""
        self._cleanup_expired()

        candidates = [
            v for v in self.knowledge.values()
            if v.get('relevance', 0) >= 0.2 and v.get('my_angle')
        ]
        candidates.sort(key=lambda x: x['relevance'], reverse=True)

        return candidates[:limit]

    def get_all_keywords(self) -> List[str]:
        """모든 키워드 목록"""
        self._cleanup_expired()
        return list(self.knowledge.keys())

    def get_stats(self) -> Dict:
        """통계"""
        self._cleanup_expired()
        if not self.knowledge:
            return {"total": 0, "relevant": 0, "avg_relevance": 0}

        relevances = [v.get('relevance', 0) for v in self.knowledge.values()]
        return {
            "total": len(self.knowledge),
            "relevant": len([r for r in relevances if r >= 0.3]),
            "avg_relevance": sum(relevances) / len(relevances) if relevances else 0
        }


knowledge_base = KnowledgeBase()
