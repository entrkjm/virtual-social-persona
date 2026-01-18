"""
Twitter Trend Learner
Twitter에서 트렌드 컨텍스트 수집 (플랫폼 종속적)
"""
from typing import Dict, List, Optional
from platforms.twitter.social import search_tweets


def fetch_trend_context(keyword: str, count: int = 5) -> List[Dict]:
    """
    Twitter에서 키워드 관련 트윗 검색
    
    Returns:
        List of dicts: [{"user": ..., "text": ..., "id": ...}, ...]
    """
    if not keyword or len(keyword) < 2:
        return []
    
    try:
        tweets = search_tweets(keyword, count=count)
        return tweets or []
    except Exception as e:
        print(f"[TrendLearner] Failed to fetch '{keyword}': {e}")
        return []


def format_tweets_for_learning(tweets: List[Dict]) -> str:
    """
    트윗 목록을 학습용 텍스트로 포맷
    """
    if not tweets:
        return ""
    
    return "\n".join([
        f"- @{t.get('user', 'unknown')}: {t.get('text', '')[:100]}"
        for t in tweets[:5]
    ])
