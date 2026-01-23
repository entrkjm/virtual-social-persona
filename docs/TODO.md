# TODO / Known Issues

## Quote Notification Detection (2026-01-23)

**상태**: 미해결 (낮은 우선순위)

**문제**:
- Quote 알림의 `icon.id`가 무엇인지 확인 필요
- 현재 알림 목록에 quote 알림이 없어서 테스트 불가
- 블락한 사용자의 quote 알림은 API에서 반환되지 않음

**현재 icon 타입**:
- `bird_icon` → system (login)
- `heart_icon` → like
- `person_icon` → follow
- `retweet_icon` → repost
- `???` → quote (미확인)

**해결 방법**:
1. 다른 계정으로 직접 인용해서 icon 확인
2. twikit 소스코드에서 notification 파싱 로직 확인

**관련 파일**:
- `agent/platforms/twitter/api/social.py` - `_classify_notification_type()`
