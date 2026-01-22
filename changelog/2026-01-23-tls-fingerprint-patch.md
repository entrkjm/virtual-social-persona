# TLS Fingerprint Patch + Search Delay Fix

**Date**: 2026-01-23
**Branch**: feature/tls-fingerprint-patch
**Author**: Claude

## Summary
Twitter 226 (봇 탐지) 에러 해결을 위한 TLS fingerprint 패치. curl_cffi를 사용해 Chrome 브라우저의 TLS fingerprint 모방.

## Changes

### 1. TLS Fingerprint Patch
- `agent/platforms/twitter/api/tls_patch.py` (NEW): curl_cffi 기반 twikit 패치
  - httpx.AsyncClient 대신 curl_cffi.AsyncSession 사용
  - Chrome 120 TLS fingerprint 모방
  - CookieJar 호환 래퍼 구현

- `agent/platforms/twitter/api/social.py`: tls_patch import 추가

### 2. Search Params Fix
- `agent/platforms/twitter/api/tls_patch.py`: `params` 파라미터 지원 추가
  - GraphQL API 호출 시 features가 누락되는 400 에러 수정

### 3. Search Delay Fix
- `agent/bot.py`: Feed search retry 딜레이 위치 수정
  - 기존: 검색 후 딜레이 (의미 없음)
  - 변경: 검색 전 딜레이 (올바른 위치)

## Technical Details

### TLS Fingerprint란?
- HTTPS 연결 시 클라이언트가 보내는 ClientHello 메시지의 고유 패턴
- Python httpx vs Chrome 브라우저의 패턴이 다름
- Twitter가 이를 감지해 봇으로 판단 → 226 에러

### 해결 방법
- curl_cffi 라이브러리: libcurl을 Python에서 사용
- `impersonate="chrome120"` 옵션으로 Chrome TLS fingerprint 모방
- twikit의 httpx.AsyncClient를 curl_cffi로 monkey-patch

## Impact
- 226 에러 발생 빈도 대폭 감소
- 피드 검색, 알림 조회, 트윗 작성 등 모든 API 정상 작동

## Testing
```bash
# TLS patch 테스트
python scripts/test_tls_patch.py

# search_tweet 테스트
python -c "
import agent.platforms.twitter.api.tls_patch
from twikit import Client
import asyncio

async def test():
    client = Client('en-US')
    client.load_cookies('data/cookies/chef_choi_cookies.json')
    results = await client.search_tweet('요리', 'Latest', count=3)
    print(f'Got {len(results)} tweets')

asyncio.run(test())
"
```

## Dependencies Added
- `curl_cffi>=0.5.0`: TLS fingerprint 모방용 라이브러리
