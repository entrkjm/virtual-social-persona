# Read Replies Context

**Date**: 2026-01-23
**Branch**: feature/read-replies-context
**Author**: Claude

## Summary
피드 게시물 처리 시 기존 답글을 읽어와서 맥락 파악에 활용. 답글 읽기 딜레이 추가.

## Changes

### 1. Engine (engine.py)
- 피드 게시물 처리 시 `get_tweet_replies()` 호출
- 답글 읽기 딜레이 추가 (답글당 1-2초, 최대 8초)
- 답글을 `post['replies']`로 저장하여 하위 컴포넌트에 전달

### 2. EngagementJudge (engagement_judge.py)
- `extra_context['replies']`로 기존 답글 정보 수신
- 시스템 프롬프트에 "기존 답글 있으면 reply 안 함" 규칙 추가
- 프롬프트에 기존 답글 5개까지 표시

### 3. ReplyGenerator (reply_generator.py)
- `context['existing_replies']`로 기존 답글 정보 수신
- 프롬프트에 기존 답글 표시 + "겹치지 않는 새로운 내용" 지시

### 4. Scenarios (interesting_post.py, familiar_person.py)
- `_judge()`에서 replies를 extra_context로 전달
- `_execute_actions()`에서 replies를 context로 전달

## Expected Logs
```
[Feed] Reading @user's post (4.5s)
[Feed] Reading 3 replies...
[Judge] ...
```

## Impact
- API 호출 증가: 게시물당 +1회 (replies 가져오기)
- 처리 시간 증가: 답글 읽기 딜레이
- 답글 품질 향상: 기존 답글과 중복 방지, 맥락에 맞는 답글

## Related
- 사용자 요청: 게시물 댓글도 같이 읽어서 맥락 파악
