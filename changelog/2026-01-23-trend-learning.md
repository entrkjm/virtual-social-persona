# Trend Learning Per Session

**Date**: 2026-01-23
**Branch**: feature/learning-mode
**Author**: Claude

## Summary
매 세션 시작 시 트렌드를 확인하고, 이전 세션과 달라졌을 때만 학습.

## Changes

### 1. TrendTracker (trends.py)
- `TrendTracker` 클래스 추가
- `_previous_trends`: 이전 세션의 트렌드 저장
- `check_and_learn()`: 트렌드 확인 → 변경 감지 → 새 트렌드만 학습
- 싱글톤 `trend_tracker` 인스턴스 제공

### 2. Main Loop (main.py)
- 매 세션 시작 시 `trend_tracker.check_and_learn()` 호출
- 변경 시: `[TRENDS] New: [...], learned N`
- 변경 없음: `[TRENDS] No change since last session` (debug 레벨)

## Expected Logs
```
[TRENDS] New: ['키워드1', '키워드2'], learned 2
[SESSION 1] Mode: social (roll=0.45)
...
[TRENDS] No change since last session
[SESSION 2] Mode: social (roll=0.82)
```

## Impact
- 불필요한 LLM 호출 방지 (트렌드 변경 시에만 학습)
- 매 세션마다 트렌드 인식
- knowledge_base에 새 트렌드 컨텍스트 축적

## Related
- 기존 `get_trending_topics()` 활용
- `knowledge_base.learn_topic()` 연동
