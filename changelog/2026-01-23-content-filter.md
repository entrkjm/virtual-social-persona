# Content Filter for Incomprehensible Posts

**Date**: 2026-01-23
**Branch**: feature/content-filter
**Author**: Claude

## Summary
이해할 수 없는 포스트(외국어, 이모지만, 너무 짧음 등)를 스킵하는 필터 추가. 페르소나별 설정 가능.

## Changes

### 1. content_filter.yaml (NEW)
`personas/chef_choi/platforms/twitter/content_filter.yaml`
- 페르소나별 콘텐츠 필터 설정
- Rule-based pre-filter 설정:
  - `min_text_length`: 최소 텍스트 길이
  - `min_readable_ratio`: 읽을 수 있는 문자 비율
  - `skip_emoji_only`: 이모지만 있는 포스트 스킵
  - `supported_languages`: 지원 언어 (ko, en)
  - `skip_patterns`: 스킵 패턴 (RT @, 숫자만)
- LLM hints:
  - `feed_filter`: FeedFilter 프롬프트에 추가할 지시
  - `engagement_judge`: EngagementJudge 프롬프트에 추가할 지시

### 2. FeedFilter (feed_filter.py)
- `_rule_based_pre_filter()`: LLM 호출 전 빠른 필터링
- content_filter.yaml 로드 및 적용
- 프롬프트에 "이해불가 → fail" 추가
- 필터링 사유 로깅 (`too_short`, `emoji_only`, `unsupported_language`, `pattern_*`)

### 3. EngagementJudge (engagement_judge.py)
- 생성자에 `persona_id` 파라미터 추가
- content_filter.yaml의 llm_hints 적용
- 프롬프트에 "모르면 skip" 추가

### 4. Scenarios (5개)
- `interesting_post.py`, `familiar_person.py`
- `received_comment.py`, `mentioned.py`, `quoted.py`
- EngagementJudge에 `persona_id` 전달

### 5. FeedJourney (feed.py)
- FeedFilter에 `persona_id` 전달

## Expected Logs
```
[FeedFilter] Pre-filter: 3/10 filtered
[FeedFilter] 7/10 posts passed
[Judge] Result: like=False, repost=False, reply=False (reason: 외국어 비율 높음)
```

## Impact
- LLM 토큰 절약: rule-based pre-filter로 불필요한 LLM 호출 감소
- 더 정확한 판단: 이해 못하는 콘텐츠에 대한 잘못된 반응 방지
- 페르소나 이식성: 영문 페르소나는 다른 content_filter.yaml 사용 가능

## Related
- FeedFilter 기존 언어 필터와 병행 동작 (하위 호환)
- 새 페르소나 생성 시 content_filter.yaml 복사 필요
