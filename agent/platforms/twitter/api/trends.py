"""
Twitter Trends (Layer 3)
트위터 실시간 트렌드 수집 + 지식 학습
"""
from twikit import Client
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

_knowledge_base = None
_persona_domain = None

def _get_knowledge_base():
    """Lazy import to avoid circular dependency"""
    global _knowledge_base
    if _knowledge_base is None:
        from agent.knowledge.knowledge_base import knowledge_base
        _knowledge_base = knowledge_base
    return _knowledge_base

def _get_fallback_topics():
    """Lazy import for persona fallback topics"""
    global _persona_domain
    if _persona_domain is None:
        try:
            from agent.persona.persona_loader import active_persona
            _persona_domain = active_persona.domain
        except:
            return ["topic"]
    return _persona_domain.fallback_topics if _persona_domain and _persona_domain.fallback_topics else ["topic"]


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
            # 트렌드 지식 학습 (비동기로 나중에 해도 됨)
            _learn_trends_async(trends)
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
        return _get_fallback_topics()


def get_daily_briefing():
    """오늘의 트렌드 브리핑 / Daily trend briefing"""
    trends = get_trending_topics(count=5)
    if not trends:
        return "트렌드 정보 없음"
    return f"오늘의 이슈: {', '.join(trends)}"


def _learn_trends_async(trends: list):
    """트렌드 키워드 지식 학습 (최대 3개만)"""
    try:
        kb = _get_knowledge_base()
        learned = 0
        for keyword in trends[:3]:  # 너무 많으면 LLM 호출 비용
            existing = kb.get(keyword)
            if not existing:
                kb.learn_topic(keyword)
                learned += 1
        if learned:
            print(f"[TRENDS] Learned {learned} new topics")
    except Exception as e:
        print(f"[TRENDS] Learn failed: {e}")


class TrendTracker:
    """
    트렌드 변경 감지 및 학습
    매 세션마다 호출, 변경 없으면 스킵
    """

    def __init__(self):
        self._previous_trends: set = set()

    def check_and_learn(self, count: int = 5) -> dict:
        """
        트렌드 확인 → 변경 감지 → 학습

        Returns:
            {
                "checked": bool,
                "changed": bool,
                "new_trends": list,
                "learned": int
            }
        """
        result = {
            "checked": False,
            "changed": False,
            "new_trends": [],
            "learned": 0
        }

        try:
            current_trends = get_trending_topics(count=count)
            if not current_trends:
                return result

            result["checked"] = True
            current_set = set(current_trends)

            # 변경 감지
            new_trends = current_set - self._previous_trends
            if not new_trends:
                # 변경 없음 - 스킵
                return result

            result["changed"] = True
            result["new_trends"] = list(new_trends)

            # 새 트렌드만 학습
            kb = _get_knowledge_base()
            learned = 0
            for keyword in list(new_trends)[:3]:
                existing = kb.get(keyword)
                if not existing:
                    kb.learn_topic(keyword)
                    learned += 1

            result["learned"] = learned

            # 이전 트렌드 업데이트
            self._previous_trends = current_set

            return result

        except Exception as e:
            print(f"[TrendTracker] Error: {e}")
            return result


# 싱글톤 인스턴스
trend_tracker = TrendTracker()
