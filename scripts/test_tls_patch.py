#!/usr/bin/env python3
"""
TLS Patch 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 패치 먼저 로드
print("Loading TLS patch...")
import agent.platforms.twitter.api.tls_patch

# 그 다음 twikit
print("Loading twikit...")
from twikit import Client

import asyncio


async def test_client():
    print("\n=== Testing patched twikit client ===")

    client = Client('en-US')
    print(f"Client http type: {type(client.http)}")

    # 쿠키 로드 테스트
    cookies_file = "data/cookies/chef_choi_cookies.json"
    if os.path.exists(cookies_file):
        print(f"Loading cookies from {cookies_file}...")
        try:
            client.load_cookies(cookies_file)
            print("✅ Cookies loaded")
        except Exception as e:
            print(f"❌ Cookie load failed: {e}")
            return

    # 간단한 API 호출 테스트
    print("\nTesting API call...")
    try:
        me = await client.user()
        print(f"✅ Logged in as @{me.screen_name}")
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return

    print("\n=== Patch test complete ===")


if __name__ == "__main__":
    asyncio.run(test_client())
