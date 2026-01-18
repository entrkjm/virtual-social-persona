import unittest
from datetime import datetime
from agent.platforms.interface import SocialPlatformAdapter, SocialPost, SocialUser
from agent.bot import SocialAgent
# Mock persona loader if needed, or rely on existing files loading
# agent.bot imports active_persona globally, so it should load.

class MockAdapter(SocialPlatformAdapter):
    def __init__(self):
        self.search_called = False
        self.post_called = False
        self.posts = []
        
    def search(self, query: str, count: int = 10):
        self.search_called = True
        print(f"[Mock] searching: {query}")
        # Return dummy posts
        user = SocialUser(id="u1", username="testuser", name="Test User")
        return [
            SocialPost(
                id="p1", 
                text="Kimchi is great! #kfood", 
                user=user, 
                created_at=datetime.now(),
                metrics={"likes": 10, "reposts": 5, "replies": 1}
            )
        ]

    def get_mentions(self, count: int = 20):
        return []

    def post(self, content: str, media_paths=None):
        self.post_called = True
        print(f"[Mock] posted: {content}")
        return "mock_post_id"

    def reply(self, to_post_id, content, media_paths=None):
        print(f"[Mock] replied to {to_post_id}: {content}")
        return "mock_reply_id"

    def like(self, post_id):
        print(f"[Mock] liked {post_id}")
        return True

    def repost(self, post_id):
        print(f"[Mock] reposted {post_id}")
        return True

    def get_post(self, post_id):
        return None
        
    def follow(self, user_id):
        return True
        
    def get_user(self, user_id=None, username=None):
        return SocialUser(id="u1", username="testuser", name="Test User")

def test_workflow():
    print("Testing SocialAgent with MockAdapter...")
    adapter = MockAdapter()
    agent = SocialAgent(adapter)
    
    print("Running scout_and_respond...")
    # This might fail if LLM or other components act up, but we want to verify structure
    try:
        status, msg, data = agent.scout_and_respond()
        print(f"Result: {status}, {msg}")
    except Exception as e:
        print(f"Execution failed (expected if external deps missing, but check structure): {e}")

    if adapter.search_called:
        print("✅ Adapter.search was called (Decoupling Success)")
    else:
        print("❌ Adapter.search was NOT called")

if __name__ == "__main__":
    test_workflow()
