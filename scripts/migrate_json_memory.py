"""
JSON Memory Migration
기존 agent_memory.json → SQLite 마이그레이션
Migrate legacy JSON memory to SQLite
"""
import json
import os
from datetime import datetime
from typing import Dict, List

# Project root에서 실행되도록 path 설정
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.memory.database import memory_db, Episode, Relationship, generate_id


def load_json_memory(json_path: str = "agent_memory.json") -> Dict:
    """JSON 메모리 파일 로드"""
    if not os.path.exists(json_path):
        print(f"[MIGRATION] JSON file not found: {json_path}")
        return {"interactions": [], "facts": {}}

    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def migrate_interactions(interactions: List[Dict]) -> Dict[str, int]:
    """상호작용 데이터를 Episodes로 마이그레이션"""
    stats = {"episodes": 0, "relationships": 0, "skipped": 0}

    for interaction in interactions:
        try:
            # Parse timestamp
            timestamp_str = interaction.get("timestamp", "")
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                timestamp = datetime.now()

            user_handle = interaction.get("user", "unknown")
            original_post = interaction.get("post", "")
            our_reply = interaction.get("reply", "")
            tweet_id = interaction.get("tweet_id")

            # 1. 원본 트윗을 에피소드로 저장 (saw_tweet)
            saw_episode = Episode(
                id=generate_id(),
                timestamp=timestamp,
                type="saw_tweet",
                source_id=tweet_id,
                source_user=user_handle,
                content=original_post,
                topics=_extract_simple_topics(original_post),
                sentiment="neutral",
                emotional_impact=0.5
            )
            memory_db.add_episode(saw_episode)
            stats["episodes"] += 1

            # 2. 우리 답글도 에피소드로 저장 (replied)
            if our_reply:
                reply_episode = Episode(
                    id=generate_id(),
                    timestamp=timestamp,
                    type="replied",
                    source_id=tweet_id,
                    source_user=user_handle,
                    content=our_reply,
                    topics=_extract_simple_topics(our_reply),
                    sentiment="neutral",
                    emotional_impact=0.6
                )
                memory_db.add_episode(reply_episode)
                stats["episodes"] += 1

            # 3. 관계 업데이트
            rel = memory_db.get_or_create_relationship(f"@{user_handle}")
            rel.interaction_count += 1
            rel.my_reply_count += 1
            rel.last_interaction_at = timestamp
            if not rel.common_topics:
                rel.common_topics = []
            rel.common_topics.extend(_extract_simple_topics(original_post)[:2])
            rel.common_topics = list(set(rel.common_topics))[:5]  # 최대 5개 유지
            memory_db.update_relationship(rel)
            stats["relationships"] += 1

        except Exception as e:
            print(f"[MIGRATION] Error processing interaction: {e}")
            stats["skipped"] += 1
            continue

    return stats


def _extract_simple_topics(text: str) -> List[str]:
    """간단한 키워드 추출 (LLM 없이)"""
    keywords = ["요리", "음식", "맛", "레시피", "식감", "조리", "재료",
                "파스타", "고기", "채소", "해물", "칼국수", "오징어",
                "베이킹", "구이", "조림", "볶음"]

    found = []
    text_lower = text.lower()
    for kw in keywords:
        if kw in text_lower:
            found.append(kw)

    return found if found else ["general"]


def migrate_facts(facts: Dict) -> int:
    """facts 데이터 마이그레이션 (현재 비어있음)"""
    # facts가 비어있으면 스킵
    if not facts:
        return 0

    # TODO: facts 구조가 정의되면 마이그레이션 로직 추가
    return 0


def run_migration(json_path: str = "agent_memory.json", backup: bool = True):
    """전체 마이그레이션 실행"""
    print("=" * 50)
    print("[MIGRATION] Starting JSON → SQLite migration")
    print("=" * 50)

    # 1. JSON 로드
    data = load_json_memory(json_path)
    interactions = data.get("interactions", [])
    facts = data.get("facts", {})

    print(f"[MIGRATION] Found {len(interactions)} interactions, {len(facts)} facts")

    # 2. 백업 생성
    if backup and os.path.exists(json_path):
        backup_path = f"{json_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy(json_path, backup_path)
        print(f"[MIGRATION] Backup created: {backup_path}")

    # 3. 마이그레이션 실행
    interaction_stats = migrate_interactions(interactions)
    facts_count = migrate_facts(facts)

    # 4. 결과 출력
    print("=" * 50)
    print("[MIGRATION] Complete!")
    print(f"  - Episodes created: {interaction_stats['episodes']}")
    print(f"  - Relationships updated: {interaction_stats['relationships']}")
    print(f"  - Facts migrated: {facts_count}")
    print(f"  - Skipped: {interaction_stats['skipped']}")
    print("=" * 50)

    return {
        "episodes": interaction_stats["episodes"],
        "relationships": interaction_stats["relationships"],
        "facts": facts_count,
        "skipped": interaction_stats["skipped"]
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate JSON memory to SQLite")
    parser.add_argument(
        "--json-path",
        default="agent_memory.json",
        help="Path to JSON memory file"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup"
    )

    args = parser.parse_args()
    run_migration(json_path=args.json_path, backup=not args.no_backup)
