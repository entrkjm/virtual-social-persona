"""
Twitter Trends (Layer 3)
트위터 실시간 트렌드 수집
"""
from twikit import Client
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()


def get_trending_topics(count=5):
    try:
        client = Client('ko-KR')

        auth_token = os.getenv("TWITTER_AUTH_TOKEN")
        ct0 = os.getenv("TWITTER_CT0")

        if auth_token and ct0:
            client.set_cookies({
                'auth_token': auth_token,
                'ct0': ct0
            })
        else:
            print("[TRENDS] No cookies")
            return []

        # 기존 이벤트 루프 확인
        try:
            loop = asyncio.get_running_loop()
            # 이미 루프가 있으면 nest_asyncio 필요 → 그냥 스킵
            print("[TRENDS] Event loop conflict, skipping")
            return []
        except RuntimeError:
            # 루프 없음 - 새로 생성
            pass

        trends = asyncio.run(
            asyncio.wait_for(_fetch_trends_async(client, count), timeout=5)
        )
        if trends:
            print(f"[TRENDS] {len(trends)} topics fetched")
        return trends

    except asyncio.TimeoutError:
        print("[TRENDS] Timeout (5s)")
        return []
    except Exception as e:
        print(f"[TRENDS] Error: {e}")
        return []


async def _fetch_trends_async(client, count):
    try:
        trends_data = await client.get_trends(
            'trending',
            count=count,
            retry=False,
            additional_request_params={'candidate_source': 'trends'}
        )
        if not trends_data:
            return []

        trend_keywords = []
        for trend in trends_data[:count]:
            if hasattr(trend, 'name'):
                trend_keywords.append(trend.name.replace('#', ''))
        return trend_keywords

    except Exception as e:
        print(f"[TRENDS] {e}")
        return ["요리", "맛집", "레시피"]  # fallback


def get_daily_briefing():
    """오늘의 트렌드 브리핑 / Daily trend briefing"""
    trends = get_trending_topics(count=5)
    if not trends:
        return "트렌드 정보 없음"
    return f"오늘의 이슈: {', '.join(trends)}"
