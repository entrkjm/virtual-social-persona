from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class SocialUser:
    id: str
    username: str  # @handle
    name: str      # Display Name
    bio: str = ""
    followers_count: int = 0
    following_count: int = 0
    is_verified: bool = False

@dataclass
class SocialPost:
    id: str
    text: str
    user: SocialUser
    created_at: datetime
    metrics: Dict[str, int] = field(default_factory=lambda: {"likes": 0, "reposts": 0, "replies": 0})
    url: str = ""
    is_reply: bool = False
    reply_to_id: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict) # Platform specific raw data

class SocialPlatformAdapter(ABC):
    """Abstract Base Class for Social Media Platforms"""

    @abstractmethod
    def search(self, query: str, count: int = 10) -> List[SocialPost]:
        """Search for posts matching the query"""
        pass

    @abstractmethod
    def get_mentions(self, count: int = 20) -> List[SocialPost]:
        """Get recent mentions of the authenticated user"""
        pass

    @abstractmethod
    def post(self, content: str, media_paths: List[str] = None) -> Optional[str]:
        """Create a new post. Returns ID of the new post."""
        pass

    @abstractmethod
    def reply(self, to_post_id: str, content: str, media_paths: List[str] = None) -> Optional[str]:
        """Reply to a post. Returns ID of the reply."""
        pass

    @abstractmethod
    def like(self, post_id: str) -> bool:
        """Like a post"""
        pass

    @abstractmethod
    def repost(self, post_id: str) -> bool:
        """Repost/Retweet a post"""
        pass

    @abstractmethod
    def get_post(self, post_id: str) -> Optional[SocialPost]:
        """Get a specific post by ID"""
        pass
        
    @abstractmethod
    def follow(self, user_id: str) -> bool:
        """Follow a user"""
        pass

    @abstractmethod
    def get_user(self, user_id: str = None, username: str = None) -> Optional[SocialUser]:
        """Get user profile"""
        pass
