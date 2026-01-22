# 듀얼 페르소나 소통 설정

두 페르소나가 서로 주로 소통하고, 다른 활동은 최소화하는 설정.

## activity.yaml

```yaml
# 모드 가중치 - social만
mode_weights:
  social: 1.0      # 100% 소셜 모드
  casual: 0.0      # 독립 포스팅 X
  series: 0.0      # 시리즈 X

# Journey 가중치 - 알림 위주
social:
  journey_weights:
    notification: 0.95   # 알림 95% (서로의 멘션/댓글)
    feed: 0.05           # 피드 5% (다른 사람 글 거의 안 봄)

  feed_selection:
    familiar_first: true          # 아는 사람 우선
    random_discovery_prob: 0.0    # 랜덤 발견 X
```

## core_relationships.yaml

각 페르소나에서 상대방을 등록:

```yaml
# 페르소나 A의 core_relationships.yaml
relationships:
  - username: "페르소나B_handle"
    type: "close_friend"
    priority: 1.0
    always_reply: true

# 페르소나 B의 core_relationships.yaml
relationships:
  - username: "페르소나A_handle"
    type: "close_friend"
    priority: 1.0
    always_reply: true
```

## 결과 예상

| 활동 | 비율 |
|------|------|
| 서로 알림 반응 | ~95% |
| 다른 사람 글 반응 | ~5% |
| 독립 포스팅 | 0% |

## 주의사항

- 둘만 100% 소통하면 자작극 탐지 위험
- 최소 5-10%는 다른 활동 권장
- 각 페르소나별 다른 IP/프록시 사용 필수
- activity_schedule에 시간 offset 권장 (2-3시간)

## 빠른 테스트용 step_interval

```yaml
# 테스트 시 빠른 확인용
step_interval:
  min: 15
  max: 45
```

프로덕션에서는 세션 기반 구조 권장.
