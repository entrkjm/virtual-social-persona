"""
Twitter API via Twikit
트위터 API 래퍼 - 포스트, 검색, 좋아요, 멘션, 알림
Wrapper for Twitter API using Twikit

확장성: 추후 Twitter API v2 전환 시 _search_tweets_twikit만 교체
"""
import os
import asyncio
from typing import TypedDict, Optional, List
from twikit import Client
from config.settings import settings


class TweetEngagement(TypedDict, total=False):
    """트윗 engagement 메트릭 (확장 가능)"""
    favorite_count: int
    retweet_count: int
    reply_count: int
    quote_count: int
    view_count: Optional[int]
    bookmark_count: int


class TweetData(TypedDict, total=False):
    """통합 트윗 데이터 구조 (twikit/Twitter API v2 공용)"""
    id: str
    user: str
    text: str
    created_at: str
    engagement: TweetEngagement

COOKIES_FILE = os.path.join(settings.DATA_DIR, "twitter_cookies.json")


async def _get_twikit_client():
    """
    Twikit 클라이언트 생성
    1. 쿠키 파일 있으면 로드
    2. 없거나 만료되면 로그인 후 저장
    """
    client = Client('en-US')

    # 쿠키 파일 로드 시도
    if os.path.exists(COOKIES_FILE):
        try:
            client.load_cookies(COOKIES_FILE)
            print("[TWITTER] 쿠키 로드 성공")
            return client
        except Exception as e:
            print(f"[TWITTER] 쿠키 로드 실패: {e}")

    # 환경변수 쿠키 시도 (기존 방식 fallback)
    auth_token = os.getenv("TWITTER_AUTH_TOKEN")
    ct0 = os.getenv("TWITTER_CT0")
    if auth_token and ct0:
        client.set_cookies({"auth_token": auth_token, "ct0": ct0})
        print("[TWITTER] 환경변수 쿠키 사용")
        return client

    # 로그인
    await _login_and_save(client)
    return client


async def _login_and_save(client: Client):
    """로그인 후 쿠키 저장"""
    username = os.getenv("TWITTER_USERNAME")
    email = os.getenv("TWITTER_EMAIL")
    password = os.getenv("TWITTER_PASSWORD")

    if not (username and password):
        raise ValueError("Twitter credentials missing in .env")

    print("[TWITTER] 로그인 시도...")
    await client.login(auth_info_1=username, auth_info_2=email, password=password)

    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
    client.save_cookies(COOKIES_FILE)
    print(f"[TWITTER] 로그인 성공, 쿠키 저장: {COOKIES_FILE}")


def _is_session_expired(error: Exception) -> bool:
    """세션 만료 에러인지 확인"""
    err_str = str(error).lower()
    return any(kw in err_str for kw in ['unauthorized', '401', 'session', 'expired', 'login'])


async def _with_retry(func, *args, **kwargs):
    """세션 만료 시 재로그인 후 재시도"""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if _is_session_expired(e):
            print(f"[TWITTER] 세션 만료 감지, 재로그인...")
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
            return await func(*args, **kwargs)
        raise


async def _post_tweet_twikit(content: str, reply_to: str = None):
    async def _do():
        client = await _get_twikit_client()
        if reply_to:
            tweet = await client.create_tweet(text=content, reply_to=reply_to)
        else:
            tweet = await client.create_tweet(text=content)
        return tweet.id
    return await _with_retry(_do)


def _extract_engagement(tweet) -> TweetEngagement:
    """twikit Tweet 객체에서 engagement 추출 (안전하게)"""
    return {
        'favorite_count': getattr(tweet, 'favorite_count', 0) or 0,
        'retweet_count': getattr(tweet, 'retweet_count', 0) or 0,
        'reply_count': getattr(tweet, 'reply_count', 0) or 0,
        'quote_count': getattr(tweet, 'quote_count', 0) or 0,
        'view_count': getattr(tweet, 'view_count', None),
        'bookmark_count': getattr(tweet, 'bookmark_count', 0) or 0,
    }


async def _search_tweets_twikit(query: str, count: int = 5) -> List[TweetData]:
    async def _do():
        client = await _get_twikit_client()
        tweets = await client.search_tweet(query, product='Latest')
        results: List[TweetData] = []
        for t in tweets[:count]:
            results.append({
                "id": t.id,
                "user": t.user.screen_name,
                "text": t.text,
                "created_at": t.created_at,
                "engagement": _extract_engagement(t)
            })
        return results
    return await _with_retry(_do)


def _twitter_weighted_len(text: str) -> int:
    """Twitter 가중치 글자수 (한글/한자/일본어 = 2, 나머지 = 1)"""
    count = 0
    for char in text:
        if '\u1100' <= char <= '\u11FF' or '\u3130' <= char <= '\u318F' or '\uAC00' <= char <= '\uD7AF':
            count += 2
        elif '\u4E00' <= char <= '\u9FFF' or '\u3040' <= char <= '\u30FF':
            count += 2
        else:
            count += 1
    return count

def post_tweet(content: str, reply_to: str = None) -> str:
    """트윗 게시 / Post tweet"""
    weighted_len = _twitter_weighted_len(content)
    if weighted_len > 280:
        target_chars = len(content) * 280 // weighted_len - 3
        print(f"[TWEET] 가중치 글자수 초과 ({weighted_len}), {target_chars}자로 자름")
        content = content[:target_chars] + "..."
    try:
        tweet_id = asyncio.run(_post_tweet_twikit(content, reply_to))
        print(f"[TWEET] posted {tweet_id}")
        return str(tweet_id)
    except Exception as e:
        print(f"[TWEET] failed: {e}")
        _log_to_file("Twitter (Failed)", content)
        raise


def search_tweets(query: str, count: int = 5):
    """트윗 검색 / Search tweets"""
    try:
        return asyncio.run(_search_tweets_twikit(query, count))
    except Exception as e:
        print(f"[SEARCH] failed: {e}")
        return []


async def _favorite_tweet_twikit(tweet_id: str):
    async def _do():
        client = await _get_twikit_client()
        await client.favorite_tweet(tweet_id)
        return True
    return await _with_retry(_do)


def favorite_tweet(tweet_id: str) -> bool:
    """좋아요 / Like tweet"""
    try:
        asyncio.run(_favorite_tweet_twikit(tweet_id))
        print(f"[LIKE] {tweet_id}")
        return True
    except Exception as e:
        print(f"[LIKE] failed: {e}")
        return False


async def _repost_tweet_twikit(tweet_id: str):
    async def _do():
        client = await _get_twikit_client()
        await client.retweet(tweet_id)
        return True
    return await _with_retry(_do)


def repost_tweet(tweet_id: str) -> bool:
    """리포스트 / Retweet"""
    try:
        asyncio.run(_repost_tweet_twikit(tweet_id))
        print(f"[REPOST] {tweet_id}")
        return True
    except Exception as e:
        print(f"[REPOST] failed: {e}")
        return False


async def _get_mentions_twikit(count: int = 20):
    async def _do():
        client = await _get_twikit_client()
        notifications = await client.get_notifications('Mentions', count=count)
        results = []
        for notif in notifications:
            if notif.tweet:
                results.append({
                    "id": notif.tweet.id,
                    "user": notif.from_user.screen_name if notif.from_user else "unknown",
                    "text": notif.tweet.text,
                    "message": notif.message,
                    "timestamp": notif.timestamp_ms
                })
        return results
    return await _with_retry(_do)


def get_mentions(count: int = 20):
    """내 멘션 가져오기 / Get mentions"""
    try:
        return asyncio.run(_get_mentions_twikit(count))
    except Exception as e:
        print(f"[MENTIONS] failed: {e}")
        return []


async def _get_tweet_replies_twikit(tweet_id: str):
    async def _do():
        client = await _get_twikit_client()
        tweet = await client.get_tweet_by_id(tweet_id)
        if not tweet or not tweet.replies:
            return []
        results = []
        for reply in tweet.replies:
            results.append({
                "id": reply.id,
                "user": reply.user.screen_name if reply.user else "unknown",
                "text": reply.text,
                "created_at": reply.created_at if hasattr(reply, 'created_at') else None
            })
        return results
    return await _with_retry(_do)


def get_tweet_replies(tweet_id: str):
    """특정 트윗의 답글 가져오기 / Get replies to a tweet"""
    try:
        return asyncio.run(_get_tweet_replies_twikit(tweet_id))
    except Exception as e:
        print(f"[REPLIES] failed: {e}")
        return []


def post_threads(content: str) -> str:
    """Deprecated - Selenium 방식으로 대체됨"""
    print("[THREADS] deprecated")
    _log_to_file("Threads (Deprecated)", content)
    return "deprecated"


def _log_to_file(platform: str, content: str):
    """API 실패시 로컬 백업 / Fallback logging"""
    try:
        with open("data/posted_content.txt", "a", encoding="utf-8") as f:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] [{platform}]\n{content}\n{'-'*50}\n")
    except Exception as e:
        print(f"[LOG] failed: {e}")


# === Follow Functions ===

async def _follow_user_twikit(user_id: str):
    async def _do():
        client = await _get_twikit_client()
        await client.follow_user(user_id)
        return True
    return await _with_retry(_do)


def follow_user(user_id: str) -> bool:
    """유저 팔로우 / Follow user"""
    try:
        asyncio.run(_follow_user_twikit(user_id))
        print(f"[FOLLOW] {user_id}")
        return True
    except Exception as e:
        print(f"[FOLLOW] failed: {e}")
        return False


async def _get_user_profile_twikit(user_id: str = None, screen_name: str = None):
    async def _do():
        client = await _get_twikit_client()
        if user_id:
            user = await client.get_user_by_id(user_id)
        elif screen_name:
            user = await client.get_user_by_screen_name(screen_name)
        else:
            raise ValueError("user_id or screen_name required")

        return {
            "id": user.id,
            "screen_name": user.screen_name,
            "name": user.name,
            "bio": user.description,
            "description": user.description,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "friends_count": user.following_count,
            "profile_image": user.profile_image_url,
            "created_at": user.created_at,
            "following_me": getattr(user, 'following', False),
            "verified": getattr(user, 'verified', False)
        }
    return await _with_retry(_do)


def get_user_profile(user_id: str = None, screen_name: str = None) -> dict:
    """유저 프로필 조회 / Get user profile"""
    try:
        return asyncio.run(_get_user_profile_twikit(user_id, screen_name))
    except Exception as e:
        print(f"[PROFILE] failed: {e}")
        return {}


async def _check_is_following_twikit(user_id: str):
    async def _do():
        client = await _get_twikit_client()
        # Twikit의 relationship 확인
        user = await client.get_user_by_id(user_id)
        return getattr(user, 'following', False)
    return await _with_retry(_do)


def check_is_following(user_id: str) -> bool:
    """팔로우 여부 확인 / Check if following"""
    try:
        return asyncio.run(_check_is_following_twikit(user_id))
    except Exception as e:
        print(f"[CHECK_FOLLOW] failed: {e}")
        return False
