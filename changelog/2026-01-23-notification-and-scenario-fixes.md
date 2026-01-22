# Notification Type & Scenario Error Fixes

**Date**: 2026-01-23
**Branch**: fix/notification-and-scenario-errors
**Author**: Claude

## Summary
1. NoneType 에러 수정 (result.details가 None일 때)
2. Quote 알림 감지 개선
3. Login 알림을 시스템 타입으로 분류 (무시)

## Changes

### 1. Scenario NoneType Error Fix
`interesting_post.py`, `familiar_person.py`
- `result.details.get()` 호출 전 None 체크 추가
- `(result.details or {}).get('actions', [])` 패턴 사용

### 2. Notification Type Classification (social.py)
- **system** 타입 추가: login 관련 알림 무시
- **quote** 감지 개선: "quote tweet", "회원님의 트윗을 인용" 키워드 추가

```python
# 무시할 시스템 알림
if any(kw in msg for kw in ["login", "로그인", "logged in", "접속"]):
    return "system"

# Quote 감지 (개선)
elif any(kw in msg for kw in ["quoted", "quote tweet", "인용", "회원님의 트윗을 인용"]):
    return "quote"
```

## Expected Logs
```
# Before
[NOTIF] Unknown type: there was a login to your account...

# After
[Notification] Type breakdown: {'system': 6, 'like': 5, ...}
→ system 타입은 자동으로 무시됨
```

## Impact
- Scenario 실행 중 NoneType 에러 방지
- Login 알림이 unknown 대신 system으로 분류되어 깔끔한 로그
- Quote 알림 감지 확률 향상

## Notes
Quote 알림이 여전히 감지되지 않으면, 실제 알림 메시지를 확인해서 키워드 추가 필요.
Twitter의 알림 메시지 형식이 변경될 수 있음.
