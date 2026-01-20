"""
Twitter API via Twikit
트위터 API 래퍼 - 포스트, 검색, 좋아요, 멘션, 알림
"""
import os
import asyncio
from typing import TypedDict, Optional, List
from twikit import Client
from config.settings import settings


def _run_async(coro):
    """Run async coroutine with proper event loop handling to avoid 'Event loop is closed' errors"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


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



def _get_cookies_path() -> str:
    """
    현재 활성화된 페르소나에 맞는 쿠키 파일 경로 반환
    """
    persona_name = os.getenv("PERSONA_NAME")
    
    if persona_name:
        cookie_dir = os.path.join(settings.DATA_DIR, "cookies")
        os.makedirs(cookie_dir, exist_ok=True)
        return os.path.join(cookie_dir, f"{persona_name}_cookies.json")

    return os.path.join(settings.DATA_DIR, "twitter_cookies.json")

# 전역 클라이언트 상태

_client_instance: Optional[Client] = None
_last_cookie_mtime: float = 0.0
_current_cookie_path: Optional[str] = None

async def _get_twikit_client() -> Client:
    """
    Twikit 클라이언트 가져오기 (Singleton + Hot Reload)
    쿠키 파일이 변경되면 클라이언트를 새로 생성합니다.
    """
    global _client_instance, _last_cookie_mtime, _current_cookie_path

    cookies_file = _get_cookies_path()
    
    # Path changed?
    if _current_cookie_path != cookies_file:
         _client_instance = None
         _current_cookie_path = cookies_file
         _last_cookie_mtime = 0.0

    # 1. 파일 변경 감지
    should_reload = False
    if os.path.exists(cookies_file):
        try:
            current_mtime = os.path.getmtime(cookies_file)
            if current_mtime > _last_cookie_mtime:
                print(f"[TWITTER] 🍪 쿠키 파일 변경 감지! ({_last_cookie_mtime} -> {current_mtime})")
                should_reload = True
                _last_cookie_mtime = current_mtime
        except OSError:
            pass # 파일 읽기 실패 시 무시

    # 2. 클라이언트 초기화 또는 리로드
    if _client_instance is None or should_reload:
        print(f"[TWITTER] 🔄 클라이언트 초기화 중... (Path: {os.path.basename(cookies_file)})")
        client = Client('en-US')
        
        # 쿠키 로드 시도
        if os.path.exists(cookies_file):
            try:
                client.load_cookies(cookies_file)
                print(f"[TWITTER] ✅ 쿠키 로드 완료")
            except Exception as e:
                print(f"[TWITTER] ❌ 쿠키 로드 실패: {e}")
        
        # 환경변수 폴백 (파일 없을 때만)
        elif os.getenv("TWITTER_AUTH_TOKEN") and os.getenv("TWITTER_CT0"):
             client.set_cookies({
                 "auth_token": os.getenv("TWITTER_AUTH_TOKEN"),
                 "ct0": os.getenv("TWITTER_CT0")
             })
             print("[TWITTER] ✅ 환경변수 쿠키 사용")
        
        _client_instance = client
        _current_cookie_path = cookies_file

    return _client_instance

async def _login_and_save(client: Client):
    """(Deprecated in Hot Reload Mode) 로그인 후 쿠키 저장"""
    # ... (기존 로직 유지하되, 핫리로딩 환경에서는 외부 주입을 권장)
    username = os.getenv("TWITTER_USERNAME")
    email = os.getenv("TWITTER_EMAIL")
    password = os.getenv("TWITTER_PASSWORD")

    if username and password:
        print("[TWITTER] 로그인 시도 (Deprecated)...")
        await client.login(auth_info_1=username, auth_info_2=email, password=password)
        cookies_file = _get_cookies_path()
        os.makedirs(os.path.dirname(cookies_file), exist_ok=True)
        client.save_cookies(cookies_file)
        print(f"[TWITTER] 로그인 성공, 쿠키 저장: {cookies_file}")
    else:
        print("[TWITTER] 경고: 로그인 정보 없음, 쿠키 파일에 의존합니다.")



def _is_session_expired(error: Exception) -> bool:
    """세션 만료 에러인지 확인"""
    err_str = str(error).lower()
    return any(kw in err_str for kw in ['unauthorized', '401', 'session', 'expired', 'login'])


async def _with_retry(func, *args, **kwargs):
    """세션 만료 시 재로그인 후 재시도 (Timeout 10s)"""
    try:
        return await asyncio.wait_for(func(*args, **kwargs), timeout=15.0)
    except asyncio.TimeoutError:
        print(f"[TWITTER] Timeout (15s)")
        raise
    except Exception as e:
        if _is_session_expired(e):
            print(f"[TWITTER] 세션 만료 감지, 재로그인...")
            cookies_file = _get_cookies_path()
            if os.path.exists(cookies_file):
                os.remove(cookies_file)
            return await asyncio.wait_for(func(*args, **kwargs), timeout=15.0)
        raise


async def _upload_media_twikit(client: Client, media_files: List[str]) -> List[str]:
    """미디어 업로드 -> media_id 리스트 반환"""
    media_ids = []
    for filename in media_files:
        if not os.path.exists(filename):
            print(f"[TWITTER] Media file not found: {filename}")
            continue
        try:
            # upload_media returns a Media object or ID depending on version/endpoint
            media = await client.upload_media(filename, media_category='tweet_image')
            
            media_id = None
            if hasattr(media, 'media_id'):
                media_id = media.media_id
            elif hasattr(media, 'id'):
                media_id = media.id
            elif isinstance(media, (int, str)):
                media_id = str(media)
            else:
                print(f"[TWITTER] Unknown media response type: {type(media)}")
                continue
                
            if media_id:
                media_ids.append(media_id)
        except Exception as e:
            print(f"[TWITTER] Failed to upload media {filename}: {e}")
            import traceback
            traceback.print_exc()
    return media_ids


async def _post_tweet_twikit(content: str, reply_to: str = None, media_files: List[str] = None):
    async def _do():
        client = await _get_twikit_client()
        
        media_ids = None
        if media_files:
            media_ids = await _upload_media_twikit(client, media_files)
            
        if reply_to:
            tweet = await client.create_tweet(text=content, reply_to=reply_to, media_ids=media_ids)
        else:
            tweet = await client.create_tweet(text=content, media_ids=media_ids)
        return tweet.id
    return await _with_retry(_do)


def _extract_engagement(tweet) -> TweetEngagement:
    """twikit Tweet 객체에서 engagement 추출"""
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
    """Twitter 가중치 글자수"""
    count = 0
    for char in text:
        if '\u1100' <= char <= '\u11FF' or '\u3130' <= char <= '\u318F' or '\uAC00' <= char <= '\uD7AF':
            count += 2
        elif '\u4E00' <= char <= '\u9FFF' or '\u3040' <= char <= '\u30FF':
            count += 2
        else:
            count += 1
    return count

def post_tweet(content: str, reply_to: str = None, media_files: List[str] = None) -> str:
    """트윗 게시 / Post tweet (with optional media)"""
    weighted_len = _twitter_weighted_len(content)
    if weighted_len > 280:
        target_chars = len(content) * 280 // weighted_len - 3
        content = content[:target_chars] + "..."
    try:
        tweet_id = _run_async(_post_tweet_twikit(content, reply_to, media_files))
        print(f"[TWEET] posted {tweet_id}")
        return str(tweet_id)
    except Exception as e:
        print(f"[TWEET] failed: {e}")
        _log_to_file("Twitter (Failed)", content)
        raise


def search_tweets(query: str, count: int = 5):
    """트윗 검색 / Search tweets (with retry and query simplification)"""
    import time
    
    # 1차 시도: 원본 쿼리
    try:
        return _run_async(_search_tweets_twikit(query, count))
    except Exception as e:
        print(f"[SEARCH] 1st attempt failed: {e}")
    
    # 2차 시도: filter 제거
    import random
    time.sleep(random.uniform(2, 5))
    simplified_query = query
    for filter_term in ['-filter:links', '-filter:replies', '-filter:retweets']:
        simplified_query = simplified_query.replace(filter_term, '')
    simplified_query = ' '.join(simplified_query.split())  # 중복 공백 제거
    
    if simplified_query != query:
        try:
            print(f"[SEARCH] Retry with simplified: {simplified_query[:50]}...")
            return _run_async(_search_tweets_twikit(simplified_query, count))
        except Exception as e:
            print(f"[SEARCH] 2nd attempt failed: {e}")
    
    # 3차 시도: 키워드만 (exclusions 제거)
    time.sleep(random.uniform(2, 5))
    keywords_only = simplified_query.split()[0] if simplified_query else query.split()[0]
    try:
        print(f"[SEARCH] Retry with keyword only: {keywords_only}")
        return _run_async(_search_tweets_twikit(keywords_only, count))
    except Exception as e:
        print(f"[SEARCH] final attempt failed: {e}")
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
        _run_async(_favorite_tweet_twikit(tweet_id))
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
        _run_async(_repost_tweet_twikit(tweet_id))
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
        return _run_async(_get_mentions_twikit(count))
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
        return _run_async(_get_tweet_replies_twikit(tweet_id))
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
        _run_async(_follow_user_twikit(user_id))
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
        return _run_async(_get_user_profile_twikit(user_id, screen_name))
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
        return _run_async(_check_is_following_twikit(user_id))
    except Exception as e:
        print(f"[CHECK_FOLLOW] failed: {e}")
        return False


async def _get_my_tweets_twikit(screen_name: str, count: int = 50) -> List[dict]:
    """내 트윗 가져오기"""
    async def _do():
        client = await _get_twikit_client()
        user = await client.get_user_by_screen_name(screen_name)
        tweets = await user.get_tweets('Tweets', count=count)

        result = []
        for tweet in tweets:
            text = tweet.text or tweet.full_text or ""
            # RT는 스킵 (리트윗)
            if text.startswith("RT @"):
                continue
            result.append({
                "id": tweet.id,
                "text": text,
                "created_at": str(tweet.created_at) if tweet.created_at else None,
                "is_reply": tweet.in_reply_to is not None,
                "reply_to": tweet.in_reply_to
            })
        return result
    return await _with_retry(_do)


def get_my_tweets(screen_name: str, count: int = 50) -> List[dict]:
    """내 트윗 목록 조회 (백필용)"""
    try:
        return _run_async(_get_my_tweets_twikit(screen_name, count))
    except Exception as e:
        print(f"[MY_TWEETS] failed: {e}")
        return []

async def _get_trends_twikit(woeid: int = 23424868):
    async def _do():
        client = await _get_twikit_client()
        # get_place_trends returns trends for a specific WOEID (South Korea = 23424868)
        result = await client.get_place_trends(woeid)
        if isinstance(result, dict):
            trends = result.get('trends', [])
        else:
            trends = getattr(result, 'trends', [])
        
        return [t.get('name') if isinstance(t, dict) else getattr(t, 'name', str(t)) for t in trends]
    return await _with_retry(_do)


def get_trends(woeid: int = 23424868) -> List[str]:
    """트렌드 가져오기 (WOEID: 23424868 = South Korea)"""
    try:
        return _run_async(_get_trends_twikit(woeid))
    except Exception as e:
        print(f"[TRENDS] failed: {e}")
        return []

async def _get_new_followers_twikit(screen_name: str, count: int = 20):
    async def _do():
        client = await _get_twikit_client()
        # Twikit doesn't have a direct "new followers" since X, 
        # but we can fetch recent followers
        # user = await client.get_user_by_screen_name(screen_name)
        # followers = await user.get_followers(count=count)
        
        # Alternatively, use get_followers with user_id if we have it, 
        # but using screen_name logic:
        user = await client.get_user_by_screen_name(screen_name)
        followers = await user.get_followers(count=count)
        
        results = []
        for follower in followers:
             results.append({
                "id": follower.id,
                "screen_name": follower.screen_name,
                "name": follower.name,
                "bio": follower.description,
                "followers_count": follower.followers_count,
                 "following_count": follower.following_count,
                 "created_at": str(follower.created_at) if hasattr(follower, 'created_at') else None,
                 "profile_image_url": follower.profile_image_url,
                 "following": getattr(follower, 'following', False)
             })
        return results
    return await _with_retry(_do)

def get_new_followers(screen_name: str, count: int = 20) -> List[dict]:
    """최근 팔로워 조회"""
    try:
        return _run_async(_get_new_followers_twikit(screen_name, count))
    except Exception as e:
        print(f"[FOLLOWERS] failed: {e}")
        return []
