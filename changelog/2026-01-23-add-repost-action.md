# Add Repost Action to Social V2

**Date**: 2026-01-23
**Branch**: feature/add-repost-action
**Author**: Claude

## Summary
SocialEngine V2에서 repost 액션이 누락되어 있던 문제 수정. LLM 프롬프트와 시나리오 핸들러에 repost 옵션 추가.

## Problem
- `EngagementJudge` SYSTEM_PROMPT에 action 옵션이 `like|reply|skip` 만 있었음
- Feed 시나리오들에 `repost` 핸들러가 없었음
- 결과: 봇이 like/reply만 하고 repost를 전혀 하지 않음

## Changes
- `engagement_judge.py`: SYSTEM_PROMPT에 `repost` 옵션 추가
  - 판단 기준에 리포스트 가이드라인 추가 (정말 좋은 정보, 빈도 낮게)
  - action 옵션: `like|reply|repost|skip`

- `scenarios/feed/interesting_post.py`: repost 핸들러 추가
  - repost 성공 시 like도 함께 수행
  - 메모리 업데이트에 repost 포함

- `scenarios/feed/familiar_person.py`: repost 핸들러 추가
  - repost 성공 시 like도 함께 수행
  - 메모리 업데이트에 repost 포함

## Impact
- Feed 탐색 시 좋은 글을 리포스트할 수 있게 됨
- 더 자연스러운 소셜 미디어 활동 패턴
