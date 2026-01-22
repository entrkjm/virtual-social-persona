# Cookie Loading Fix

**Date**: 2026-01-23
**Branch**: fix/cookie-loading-issue
**Author**: Claude

## Summary
쿠키 파일 로드 로직 수정. 환경변수 fallback 제거, active_persona.yaml에서 직접 페르소나 이름 읽도록 변경.

## Problem
- `social.py`가 import될 때 `PERSONA_NAME` 환경변수가 설정되지 않음
- `persona_loader.py`가 환경변수를 설정하지만, `social.py`가 먼저 import되는 경우 fallback 경로 사용
- 결과: `twitter_cookies.json` (존재하지 않음) 대신 `chef_choi_cookies.json` 사용해야 함

## Changes

### 1. social.py - `_get_cookies_path()` 수정
- 환경변수 없으면 `config/active_persona.yaml`에서 직접 페르소나 이름 읽기
- 환경변수 쿠키 fallback 제거 (더 이상 지원 안 함)
- 쿠키 파일 없을 시 명확한 에러 로그

```python
# Before
if os.getenv("TWITTER_AUTH_TOKEN") and os.getenv("TWITTER_CT0"):
    client.set_cookies({...})
    logger.info("[TWITTER] ✅ 환경변수 쿠키 사용")

# After
if not os.path.exists(cookies_file):
    logger.error(f"[TWITTER] ❌ 쿠키 파일 없음: {cookies_file}")
```

### 2. 문서 업데이트
- `README.md`, `README_KR.md`: 환경변수 쿠키 설명 제거, 파일 기반 설명으로 변경
- `docs/ARCHITECTURE.md`: Twitter 환경변수 섹션 제거
- `docs/DEPLOYMENT_STRATEGY.md`: 멀티 페르소나 예시에서 환경변수 쿠키 제거

## Expected Logs
```
# Before (실패)
[TWITTER] ✅ 환경변수 쿠키 사용
[TWITTER] ⚠️ 계정 확인 실패: 401 Unauthorized

# After (성공)
[TWITTER] ✅ 쿠키 로드 완료: chef_choi_cookies.json
```

## Impact
- 쿠키 파일 기반 인증만 지원 (환경변수 제거)
- `data/cookies/{persona_name}_cookies.json` 경로 표준화
- 페르소나별 독립 쿠키 관리 명확화

## Migration
기존 환경변수 사용자:
1. `data/cookies/{persona_name}_cookies.json` 파일 생성
2. `TWITTER_AUTH_TOKEN`, `TWITTER_CT0` 환경변수 제거
