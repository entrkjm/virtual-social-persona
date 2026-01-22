# Profile Visit Journey

**Date**: 2026-01-22
**Branch**: feature/profile-visit-journey
**Author**: Claude

## Summary
팔로잉 중인 사람 프로필 직접 방문 기능 추가. 두 페르소나 간 상호작용 시작점 문제 해결.

## Problem
- 두 페르소나가 서로 팔로우만 하고 있으면 검색/알림으로는 접점이 안 생김
- 누군가 먼저 상대 프로필 방문해서 글에 반응해야 대화 시작

## Changes
- `activity.yaml`: profile_visit 설정 섹션 추가
  - enabled, count, target(familiar_first, random_prob), posts_to_check
- `agent/platforms/twitter/api/social.py`:
  - `get_following_list()` 함수 추가
  - `get_user_tweets()` 함수 추가
- `agent/platforms/twitter/modes/social/journeys/profile_visit.py`: 신규 파일
  - ProfileVisitJourney 클래스 구현
  - 팔로잉 목록에서 대상 선택 → 프로필 방문 → 최근 글 확인 → 상호작용
- `agent/platforms/twitter/modes/social/engine.py`:
  - session() 시그니처 확장 (get_following_list, get_user_tweets_fn 추가)
  - Phase 3: 프로필 방문 로직 추가
  - SessionResult에 profiles_visited 필드 추가
- `agent/bot.py`:
  - run_social_session()에서 새 파라미터 전달

## Config Example
```yaml
session:
  profile_visit:
    enabled: true
    count: [0, 2]           # 세션당 방문 횟수
    target:
      familiar_first: true  # affinity 높은 사람 우선
      random_prob: 0.2      # 20%는 랜덤 선택
    posts_to_check: [1, 3]  # 프로필에서 확인할 글 개수
```

## Session Flow (Updated)
```
Phase 1: 알림 처리 (3-8개)
Phase 2: 피드 탐색 (5-15개)
Phase 3: 프로필 방문 (0-2개) ← NEW
휴식 (30분-2시간)
```

## Impact
- 페르소나 간 상호작용 시작 가능
- 팔로잉 관계만으로도 대화 트리거 생성
- 세션 시간 약간 증가

## Related
- 상호작용 시작점 문제 해결
