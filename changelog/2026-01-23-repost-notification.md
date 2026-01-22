# Repost Notification Handler

**Date**: 2026-01-23
**Branch**: fix/repost-notification

## Summary
Retweet(repost) 알림에 대한 핸들러 추가. 기존에는 `retweet` 타입 알림이 시나리오 없이 필터링되었음.

## Changes

### New: RepostedScenario
- `scenarios/notification/reposted.py` 생성
- 리포스트는 직접 반응 불필요 (원본이 내 글)
- 관계 기록 + PersonMemory 업데이트에 집중
- `acknowledged` 액션 반환

### NotificationJourney
- `retweet` 타입 시나리오 핸들러 추가
- 로그 표시 개수 5 → 10 확대

## Impact
- `retweet` 알림이 더 이상 무시되지 않음
- 누가 내 글을 리포스트했는지 기록됨
- 알림 로그에서 더 많은 정보 확인 가능
