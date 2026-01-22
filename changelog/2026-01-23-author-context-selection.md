# Author Context & Smart Post Selection

**Date**: 2026-01-23
**Branch**: feature/author-context-selection
**Author**: Claude

## Summary
피드 포스트 처리 시 글쓴이 프로필을 가져오고, 전체 컨텍스트(글쓴이+댓글+포스트)를 종합해서 반응할 포스트를 선정.

## Changes

### 1. Engine (engine.py)
- `get_user_profile()` 호출로 글쓴이 프로필 수집
- 프로필 읽기 딜레이 추가 (1-2초)
- `_enrich_posts_context()`: 포스트별 컨텍스트 배치 수집
- `_select_posts_for_reaction()`: 점수 기반 포스트 선정
  - Author Score: 아는 사람(40), familiar(30), 프로필 완성도, 팔로워 수
  - Content Score: 관심 키워드 매칭 (최대 30)
  - Engagement Score: likes + retweets*2 (최대 20)
  - Reply Context Score: 댓글 적으면 참여 기회 높음 (최대 10)

### 2. EngagementJudge (engagement_judge.py)
- `extra_context['author_profile']`로 글쓴이 프로필 수신
- 프롬프트에 글쓴이 정보 표시 (screen_name, bio, followers_count)

### 3. ReplyGenerator (reply_generator.py)
- `context['author_profile']`로 글쓴이 프로필 수신
- 프롬프트에 글쓴이 정보 표시

### 4. Scenarios (interesting_post.py, familiar_person.py)
- `_judge()`에서 author_profile을 extra_context로 전달
- `_execute_actions()`에서 author_profile을 reply context로 전달

## Expected Logs
```
[Feed] Reading @user's post (4.5s)
[Feed] Author: @user - 개발자, 음식 좋아함...
[Feed] Reading 3 replies...
[Feed] Selection scores: @user1(65), @user2(45), @user3(30)
[Feed] Selected 2 posts for reaction
```

## Impact
- API 호출 증가: 포스트당 +1회 (author profile)
- 처리 시간 증가: 프로필 읽기 딜레이
- 판단 품질 향상: 글쓴이 맥락 기반 반응
- 포스트 선정 개선: 종합 점수로 가장 의미있는 포스트 선택

## Related
- 이전: read-replies-context (댓글 컨텍스트)
- 사용자 요청: 글쓴이도 파악하고 전체 보고 선정
