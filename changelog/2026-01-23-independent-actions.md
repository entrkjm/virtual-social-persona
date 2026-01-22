# Independent Actions for Social V2

**Date**: 2026-01-23
**Branch**: fix/independent-actions
**Author**: Claude

## Summary
SocialEngine V2의 액션 시스템을 독립적 boolean 구조로 변경. 기존에는 단일 action만 선택 가능했으나, 이제 like/repost/reply를 독립적으로 조합 가능.

## Problem
- `EngagementJudge`가 단일 action만 반환 (`like|reply|skip` 중 택1)
- repost 옵션 자체가 없었음
- 실제 소셜 미디어에서는 like+reply, like+repost 등 조합이 자연스러움

## Changes

### engagement_judge.py
- `JudgmentResult` 구조 변경:
  - 기존: `action: str` (단일 값)
  - 변경: `like: bool, repost: bool, reply: bool` (독립적)
- SYSTEM_PROMPT 변경:
  - 기존: `{"action": "like|reply|skip", ...}`
  - 변경: `{"like": true/false, "repost": true/false, "reply": true/false, ...}`
- 하위 호환을 위해 `action` property 유지

### scenarios/feed/interesting_post.py
- `_execute_action` → `_execute_actions` 변경
- 각 액션을 독립적으로 실행
- `actions_taken` 리스트로 실행된 액션 추적

### scenarios/feed/familiar_person.py
- 동일한 구조로 변경

## Impact
- 하나의 포스트에 like+repost, like+reply 등 다중 반응 가능
- 더 자연스러운 소셜 미디어 활동 패턴
- 하위 호환: `result.action` property로 기존 코드 동작 유지
