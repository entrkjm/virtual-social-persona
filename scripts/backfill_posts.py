"""
기존 트윗/답글 DB 백필 스크립트
Backfill existing tweets and replies to posting_history DB
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from agent.memory import agent_memory
from agent.memory.database import Episode
from agent.platforms.twitter.api.social import get_my_tweets


def backfill_posts(screen_name: str, count: int = 50):
    """기존 트윗을 DB에 백필"""
    print(f"[BACKFILL] @{screen_name}의 최근 {count}개 트윗 가져오는 중...")

    tweets = get_my_tweets(screen_name, count)
    if not tweets:
        print("[BACKFILL] 트윗을 가져오지 못했습니다.")
        return

    print(f"[BACKFILL] {len(tweets)}개 트윗 발견")

    # 기존 DB 포스팅 확인
    existing = memory_db.get_recent_posts(limit=500)
    existing_contents = {p['content'] for p in existing}

    added = 0
    skipped = 0

    for tweet in tweets:
        content = tweet['text']

        # 이미 있는지 확인
        if content in existing_contents:
            skipped += 1
            continue

        # 트윗 타입 결정
        if tweet.get('is_reply'):
            trigger_type = "backfill_reply"
        else:
            trigger_type = "backfill_post"

        # DB에 추가
        memory_db.add_posting(
            inspiration_id=None,
            content=content,
            trigger_type=trigger_type
        )
        added += 1
        print(f"  + [{trigger_type}] {content[:50]}...")

    print(f"\n[BACKFILL] 완료: {added}개 추가, {skipped}개 스킵 (이미 존재)")


def check_db_status():
    """현재 DB 상태 확인"""
    posts = memory_db.get_recent_posts(limit=100)
    print(f"\n[DB STATUS] posting_history에 {len(posts)}개 기록 있음")
    if posts:
        print("\n최근 5개:")
        for p in posts[:5]:
            print(f"  - [{p['type']}] {p['content'][:50]}...")


if __name__ == "__main__":
    # 스크린네임 설정 (환경변수 또는 직접 입력)
    screen_name = os.getenv("TWITTER_SCREEN_NAME", "")

    if not screen_name:
        print("TWITTER_SCREEN_NAME 환경변수를 설정하거나 직접 입력하세요.")
        screen_name = input("스크린네임 입력 (@ 제외): ").strip()

    if not screen_name:
        print("스크린네임이 필요합니다.")
        sys.exit(1)

    # 현재 상태 확인
    check_db_status()

    # 백필 실행
    count = int(input("\n가져올 트윗 수 (기본 50): ").strip() or "50")
    backfill_posts(screen_name, count)

    # 결과 확인
    check_db_status()
