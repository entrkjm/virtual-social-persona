import asyncio
import os
import sys
sys.path.append(os.getcwd())
from platforms.twitter.social import _post_tweet_twikit, _upload_media_twikit, _get_twikit_client

async def test_tweet():
    print("Logged in?")
    client = await _get_twikit_client()
    # print(f"User: {client.user.screen_name}")
    
    text = "테스트 트윗입니다. 텍스트가 보이시나요? (Debug Tweet)"
    image_path = "data/personas/chef_choi/series/assets/world_braised/20260119_코다리_조림/final.png"
    
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return

    print("Uploading media...")
    media_ids = await _upload_media_twikit(client, [image_path])
    print(f"Media IDs: {media_ids}")
    
    print("Posting tweet...")
    tweet_id = await _post_tweet_twikit(text, media_files=[image_path])
    print(f"Posted: https://twitter.com/user/status/{tweet_id}")

if __name__ == "__main__":
    asyncio.run(test_tweet())
