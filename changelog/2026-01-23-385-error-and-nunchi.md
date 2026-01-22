# Handle 385 Error & Add "눈치" Concept

**Date**: 2026-01-23
**Branch**: fix/385-error-and-nunchi
**Author**: Claude

## Summary
1. 385 에러 (삭제된/보이지 않는 트윗) 처리
2. "눈치" 개념 도입 - 맥락상 적절한 반응을 알 수 없으면 스킵

## Changes

### 1. social.py - 385 Error Handling
- `reply_to_tweet()`: 385 에러 시 None 반환 (graceful skip)
- 에러 로그: `[REPLY] Tweet {id} deleted or not visible (385)`

### 2. content_filter.yaml - 눈치 개념 추가
```yaml
llm_hints:
  feed_filter: |
    - "눈치" 기준: 한글이어도 어떻게 반응해야 할지 알 수 없으면 fail
      - 예: 내부 농담, 특정 커뮤니티 밈, 맥락 없는 단문, 인간관계 암시
      - 잘못 끼어들면 어색해질 수 있는 대화는 fail

  engagement_judge: |
    - "눈치" 판단: 다음 경우 skip
      - 특정 사람들끼리의 대화에 끼어드는 것 같을 때
      - 농담인지 진담인지 모호할 때
      - 반응했다가 어색해질 것 같을 때
```

### 3. FeedFilter (feed_filter.py)
- 기본 프롬프트에 "눈치" 기준 추가
- content_filter.yaml의 llm_hints 적용

### 4. EngagementJudge (engagement_judge.py)
- 기본 프롬프트에 "눈치" 판단 기준 추가
- content_filter.yaml의 llm_hints 적용

## Expected Behavior
```
# 385 에러
[REPLY] Tweet 123456 deleted or not visible (385)
→ graceful skip, 다음 포스트로 진행

# 눈치 판단
[FeedFilter] Post 789: fail (reason: 내부 농담)
[Judge] Result: skip (reason: 맥락 불분명)
```

## Impact
- 385 에러로 인한 세션 중단 방지
- 어색한 반응 감소 (눈치 기반 필터링)
- 사람다운 행동 패턴 강화

## Related
- content_filter.yaml (이전 커밋에서 추가)
- FeedFilter/EngagementJudge LLM 프롬프트
