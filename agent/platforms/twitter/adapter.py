from typing import List, Optional
from datetime import datetime
from agent.platforms.interface import SocialPlatformAdapter, SocialPost, SocialUser
import agent.platforms.twitter.api.social as twitter_api

class TwitterAdapter(SocialPlatformAdapter):
    """Adapter for Twitter using agent.platforms.twitter.api.social"""

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str: return None
        try:
            # Twitter "Wed Oct 10 20:19:24 +0000 2018"
            return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        except:
            try:
                # ISO format fallback
                return datetime.fromisoformat(date_str)
            except:
                return None

    def search(self, query: str, count: int = 10) -> List[SocialPost]:
        results = twitter_api.search_tweets(query, count)
        posts = []
        for item in results:
            created_at = item.get('created_at')
            if isinstance(created_at, str):
                created_at_dt = self._parse_date(created_at) or datetime.now()
            elif isinstance(created_at, datetime):
                created_at_dt = created_at
            else:
                created_at_dt = datetime.now()

            # User data in search result is limited, usually just username
            user = SocialUser(
                id="", 
                username=item['user'],
                name=item['user'] 
            )
            
            engagement = item.get('engagement', {})
            metrics = {
                "likes": engagement.get('favorite_count', 0),
                "reposts": engagement.get('retweet_count', 0),
                "replies": engagement.get('reply_count', 0)
            }
            
            post = SocialPost(
                id=item['id'],
                text=item['text'],
                user=user,
                created_at=created_at_dt,
                metrics=metrics,
                url=f"https://twitter.com/{item['user']}/status/{item['id']}",
                raw_data=item
            )
            posts.append(post)
        return posts

    def get_mentions(self, count: int = 20) -> List[SocialPost]:
        results = twitter_api.get_mentions(count)
        posts = []
        for item in results:
            created_at = None
            ts = item.get('timestamp')
            if ts:
                created_at = datetime.fromtimestamp(ts / 1000.0)
            else:
                created_at = datetime.now()

            user = SocialUser(
                id="",
                username=item['user'],
                name=item['user']
            )
            # Mentions API via social.py is limited in fields
            post = SocialPost(
                id=item['id'],
                text=item['text'],
                user=user,
                created_at=created_at,
                metrics={},
                url=f"https://twitter.com/{item['user']}/status/{item['id']}",
                raw_data=item
            )
            posts.append(post)
        return posts

    def post(self, content: str, media_paths: List[str] = None) -> Optional[str]:
        try:
            return twitter_api.post_tweet(content, reply_to=None, media_files=media_paths)
        except Exception as e:
            print(f"[TwitterAdapter] Post failed: {e}")
            return None

    def reply(self, to_post_id: str, content: str, media_paths: List[str] = None) -> Optional[str]:
        try:
            return twitter_api.post_tweet(content, reply_to=to_post_id, media_files=media_paths)
        except Exception as e:
            print(f"[TwitterAdapter] Reply failed: {e}")
            return None

    def like(self, post_id: str) -> bool:
        return twitter_api.favorite_tweet(post_id)

    def repost(self, post_id: str) -> bool:
        return twitter_api.repost_tweet(post_id)

    def get_post(self, post_id: str) -> Optional[SocialPost]:
        # Not implemented in social.py directly in a simple way
        # Would need to add get_tweet logic
        return None

    def follow(self, user_id: str) -> bool:
        return twitter_api.follow_user(user_id)

    def get_user(self, user_id: str = None, username: str = None) -> Optional[SocialUser]:
        profile = twitter_api.get_user_profile(user_id, username)
        if not profile:
            return None
            
        created_at_str = profile.get('created_at')
        created_at = self._parse_date(created_at_str)
        
        return SocialUser(
            id=profile.get('id', ''),
            username=profile.get('screen_name', ''),
            name=profile.get('name', ''),
            bio=profile.get('description', ''),
            followers_count=profile.get('followers_count', 0),
            following_count=profile.get('following_count', 0),
            is_verified=profile.get('verified', False),
            profile_image_url=profile.get('profile_image') or profile.get('profile_image_url', ''),
            created_at=created_at,
            following_me=profile.get('following', False), # Twikit naming might vary
            raw_data=profile
        )


    def get_trends(self, location: str = 'KR') -> List[str]:
        """트렌드 키워드 가져오기 (KR = South Korea WOEID 23424868)"""
        woeid = 23424868 if location == 'KR' else 1 # Global fallback or specific mapping
        try:
            return twitter_api.get_trends(woeid=woeid)
        except Exception as e:
            print(f"[TwitterAdapter] get_trends failed: {e}")
            return []

    def get_new_followers(self, count: int = 20) -> List[SocialUser]:
        """새 팔로워 가져오기"""
        username = os.getenv("TWITTER_USERNAME")
        if not username: return []
        
        results = twitter_api.get_new_followers(username, count)
        users = []
        for item in results:
             created_at = self._parse_date(item.get('created_at'))
             
             user = SocialUser(
                id=item['id'],
                username=item['screen_name'],
                name=item['name'],
                bio=item['bio'],
                followers_count=item['followers_count'],
                following_count=item['following_count'],
                created_at=created_at,
                profile_image_url=item['profile_image_url'],
                following_me=True, # they are followers
                is_following=item.get('following', False), # am I following them?
                raw_data=item
             )
             users.append(user)
        return users
