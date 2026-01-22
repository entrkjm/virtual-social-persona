#!/usr/bin/env python3
"""
Profile Visit Journey 단독 테스트
226 에러 없이 API 호출만 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.platforms.twitter.api import social as twitter_api
from agent.persona.persona_loader import PersonaLoader
from agent.platforms.twitter.modes.social.journeys.profile_visit import ProfileVisitJourney
from agent.memory.factory import MemoryFactory


def test_get_following_list():
    """팔로잉 목록 가져오기 테스트"""
    print("\n=== Test 1: get_following_list ===")

    screen_name = "choigangrokv"
    print(f"Fetching following list for @{screen_name}...")

    following = twitter_api.get_following_list(screen_name, count=10)

    if not following:
        print("❌ No following list returned")
        return None

    print(f"✅ Got {len(following)} users")
    for i, user in enumerate(following[:5]):
        print(f"  {i+1}. @{user.get('screen_name')} - {user.get('name')}")
        if user.get('bio'):
            print(f"     Bio: {user.get('bio')[:50]}...")

    return following


def test_get_user_tweets(following_list):
    """유저 트윗 가져오기 테스트"""
    print("\n=== Test 2: get_user_tweets ===")

    if not following_list:
        print("❌ No following list to test with")
        return None

    target = following_list[0]
    user_id = target.get('user_id')
    screen_name = target.get('screen_name')

    print(f"Fetching tweets for @{screen_name} (id={user_id})...")

    tweets = twitter_api.get_user_tweets(user_id=user_id, count=3)

    if not tweets:
        print("❌ No tweets returned")
        return None

    print(f"✅ Got {len(tweets)} tweets")
    for i, tweet in enumerate(tweets):
        text = tweet.get('text', '')[:60]
        print(f"  {i+1}. {text}...")
        eng = tweet.get('engagement', {})
        print(f"     Likes: {eng.get('favorite_count', 0)}, RTs: {eng.get('retweet_count', 0)}")

    return tweets


def test_profile_visit_journey(following_list):
    """ProfileVisitJourney 테스트 (실제 액션 없이)"""
    print("\n=== Test 3: ProfileVisitJourney ===")

    if not following_list:
        print("❌ No following list to test with")
        return

    persona_id = "chef_choi"
    loader = PersonaLoader(persona_id)
    persona_config = loader.get_full_config()

    memory_db = MemoryFactory.get_memory_db(persona_id)

    visit_cfg = persona_config.get('activity', {}).get('session', {}).get('profile_visit', {})
    print(f"Visit config: {visit_cfg}")

    journey = ProfileVisitJourney(
        memory_db=memory_db,
        platform='twitter',
        persona_config=persona_config,
        visit_config=visit_cfg
    )

    def mock_get_user_tweets(user_id=None, screen_name=None, count=5):
        print(f"  [Mock] Getting tweets for user_id={user_id}, screen_name={screen_name}")
        return twitter_api.get_user_tweets(user_id=user_id, screen_name=screen_name, count=count)

    print(f"\nRunning journey with {len(following_list)} following...")
    print("(Note: This may trigger LLM calls but will NOT post/reply due to 226)")

    try:
        result = journey.run(
            following_list=following_list,
            get_user_tweets_fn=mock_get_user_tweets,
            process_limit=1
        )

        if result:
            print(f"\n✅ Journey completed!")
            print(f"  Target: @{result.target_user}")
            print(f"  Scenario: {result.scenario_executed}")
            print(f"  Action: {result.action_taken}")
            print(f"  Success: {result.success}")
        else:
            print("\n⚠️ Journey returned None (no target selected or no posts)")

    except Exception as e:
        error_str = str(e).lower()
        if '226' in error_str:
            print(f"\n⚠️ 226 error (expected): {e}")
        else:
            print(f"\n❌ Error: {e}")
            raise


def main():
    print("=" * 50)
    print("Profile Visit Journey Test")
    print("=" * 50)

    # Test 1: get_following_list
    following = test_get_following_list()

    if not following:
        print("\n❌ Cannot proceed without following list")
        return

    # Test 2: get_user_tweets
    tweets = test_get_user_tweets(following)

    # Test 3: ProfileVisitJourney
    test_profile_visit_journey(following)

    print("\n" + "=" * 50)
    print("Test Complete")
    print("=" * 50)


if __name__ == "__main__":
    main()
