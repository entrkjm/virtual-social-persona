# Social Mode Improvements

**Date**: 2026-01-23
**Branch**: feature/social-improvements
**Author**: Claude

## Summary
소셜 모드의 품질 향상 - 중복 상호작용 방지, 답글 다양성 개선, 로그 상세화

## Changes

### 1. 이미 상호작용한 포스트 필터
- `journeys/feed.py`: `_quick_classify_hybrid`에서 `agent_memory.is_interacted()` 체크 추가
- 이미 좋아요/답글 단 포스트에 중복 상호작용 방지

### 2. Reply 유사도 체크
- `judgment/reply_generator.py`: 답글 생성 시 최근 답글과 유사도 체크
- 50% 이상 유사하면 최대 3회 재생성
- 단어 기반 유사도 계산 (`_check_similarity`, `_extract_words`)

### 3. Feed 우선순위 정렬
- `engine.py`: `_sort_posts_by_priority` 메서드 추가
- familiar → interesting → others 순서로 정렬 후 처리
- 아는 사람 글이 먼저 처리되도록 보장

### 4. Notification 로그 상세화
- `journeys/notification.py`: 처리 대상 알림 15개까지 상세 로그 출력
- 각 알림의 타입, 보낸 사람, 내용 미리보기 표시

### 5. ProfileVisit 로그 추가
- `engine.py`: ProfileVisit 스킵 사유 명시
  - disabled in config
  - no get_following_list function
  - no get_user_tweets_fn function
  - skipped (warmup mode)
  - visit_count=0 (random from [0,2])
  - No following list returned

## Files Changed
- `agent/platforms/twitter/modes/social/journeys/feed.py`
- `agent/platforms/twitter/modes/social/journeys/notification.py`
- `agent/platforms/twitter/modes/social/judgment/reply_generator.py`
- `agent/platforms/twitter/modes/social/engine.py`

## Impact
- 같은 포스트에 중복 댓글 방지
- 비슷한 답글 반복 방지 (다양성 향상)
- 아는 사람 글 우선 처리로 관계 강화
- 디버깅 용이성 향상 (상세 로그)

## Related
- 이전 대화에서 보고된 중복 댓글/유사 답글 문제 해결
