from typing import List, Optional
from datetime import datetime
from agent.platforms.interface import SocialPlatformAdapter, SocialPost, SocialUser
import platforms.twitter.social as twitter_api

class TwitterAdapter(SocialPlatformAdapter):
    """Adapter for Twitter using platforms.twitter.social"""

    def search(self, query: str, count: int = 10) -> List[SocialPost]:
        results = twitter_api.search_tweets(query, count)
        posts = []
        for item in results:
            # Convert Dict to SocialPost
            user = SocialUser(
                id="",  # Twitter search via social.py doesn't return user ID currently
                username=item['user'],
                name=item['user'] # Default to username as name is missing
            )
            
            # Parse metrics
            engagement = item.get('engagement', {})
            metrics ={
                "likes": engagement.get('favorite_count', 0),
                "reposts": engagement.get('retweet_count', 0),
                "replies": engagement.get('reply_count', 0)
            }
            
            # Parse timestamp if string
            created_at = item.get('created_at')
            if isinstance(created_at, str):
                try:
                    # Generic parser or specific format? Twikit usually returns string or datetime
                    # Assuming string for now, if it fails we might need better parsing
                    # But social.py passes it through. Let's assume it's usable or use current time as fallback
                    # Actually social.py returns raw object created_at often (datetime) or string
                    pass 
                except:
                    pass
            if not isinstance(created_at, datetime):
                # Fallback
                created_at = datetime.now()

            post = SocialPost(
                id=item['id'],
                text=item['text'],
                user=user,
                created_at=created_at,
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
                created_at=datetime.fromtimestamp(item.get('timestamp', 0) / 1000.0),
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
        return SocialUser(
            id=profile.get('id', ''),
            username=profile.get('screen_name', ''),
            name=profile.get('name', ''),
            bio=profile.get('description', ''),
            followers_count=profile.get('followers_count', 0),
            following_count=profile.get('following_count', 0),
            is_verified=profile.get('verified', False)
        )
