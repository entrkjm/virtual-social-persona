# Social Mode v2 아키텍처

## 설계 원칙

### 1. Notification-Centric
기존: Feed 탐색 → 트윗 발견 → 반응
v2: **Notification 확인 (60%)** → Feed 탐색 (40%)

이유: 내 글에 대한 반응이 관계 형성에 더 중요

### 2. HYBRID v1 (LLM 비용 최적화)
```
Feed 탐색 시:
검색 (8개) → Rule-based 분류 → 1개 선택 → LLM 판단

기존: 8-9회 LLM 호출
v2:   1-2회 LLM 호출
```

### 3. Journey → Scenario → Action
```
Journey: "무엇을 할까?" (알림 vs 피드)
    ↓
Scenario: "이 상황에서 어떻게?" (댓글 받음 / 멘션 / 아는사람 글)
    ↓
Action: "실제 실행" (좋아요 / 답글 / 팔로우)
```

---

## 컴포넌트 상세

### SocialEngineV2 (engine.py)

통합 진입점. `step()` 메서드가 한 사이클 실행.

```python
def step(posts, notification_weight=0.6):
    if random() < notification_weight:
        result = run_notification_journey()
        if result.success:
            return result

    if posts:
        result = run_feed_journey(posts)
        if result.success:
            return result

    return None
```

### NotificationJourney (journeys/notification.py)

알림 타입별 시나리오 라우팅:

| 알림 타입 | 시나리오 | 우선순위 |
|-----------|----------|----------|
| reply | ReceivedCommentScenario | 1 (최우선) |
| mention | MentionedScenario | 2 |
| quote | QuotedScenario | 3 |
| follow | NewFollowerScenario | 4 |

### FeedJourney (journeys/feed.py)

HYBRID v1 분류:

```python
def _classify_post(post):
    user_id = post.get('user_id')
    text = post.get('text', '')

    # 1. 아는 사람?
    person = memory_db.get_person(user_id)
    if person and person.tier in ('familiar', 'friend'):
        return 'familiar'

    # 2. 관심 주제?
    for keyword in core_interests:
        if keyword in text.lower():
            return 'interesting'

    return 'others'
```

### EngagementJudge (judgment/engagement_judge.py)

LLM 기반 액션 결정:

```python
# Input
- post_text: 원본 텍스트
- person: PersonMemory (있으면)
- scenario_type: 'notification_reply' | 'familiar_person_post' | etc.
- extra_context: {'is_reply_to_me': True} 등

# Output (JSON)
{
    "action": "like" | "reply" | "skip",
    "confidence": 0.0-1.0,
    "reason": "짧은 이유",
    "reply_type": "short" | "normal" | "long" | null
}
```

### ReplyGenerator (judgment/reply_generator.py)

LLM 기반 답글 생성:

```python
# persona_config에서 말투 추출
system_prompt = f"""당신은 {name}입니다.
성격: {personality}
말투: {tone}

답글 작성 규칙:
- 자연스럽고 대화체로
- 50-100자 권장
- 이모지 최소화
- 설명 없이 답글 내용만"""

# reply_type별 길이
short:  15-50자
normal: 50-100자
long:   100-150자
```

### NewFollowerScenario + FollowEngine

기존 `social/follow_engine.py` 통합:

```python
# NewFollowerScenario._judge()
def _judge(self, context):
    # 아는 사람 → 즉시 팔로우백
    if person.tier in ('familiar', 'friend'):
        return {'action': 'follow', 'use_queue': False}

    # FollowEngine으로 판단 위임
    follow_decision = self.follow_engine.should_follow(user_info, interaction_context)
    # → 점수 계산 + 봇 필터링 + 확률 결정
```

**FollowEngine 점수 계산:**
```
base_score:        50
follows_me_bonus: +30  (맞팔)
keyword_bonus:    +10  (바이오에 관심 키워드)
interaction:      +5×N (상호작용 횟수, 최대 +20)
follower_tier:    +5~10 (팔로워 수)
profile_bonus:    +5   (프로필 완성도)
───────────────────────
threshold:        40   (이상이면 팔로우 대상)
```

**봇 필터링:**
- 프로필 이미지 없음 → skip
- 바이오 5자 미만 → skip
- 팔로워/팔로잉 비율 < 0.1 → skip
- 계정 나이 < 30일 → skip
- 팔로잉 > 5000 → skip

**지연 큐:**
```python
# 즉시 실행 X → 큐에 추가
self.follow_engine.queue_follow(user_id, screen_name)
# → 30-300초 후 실행 (process_queue() 호출 시)
```

---

## 데이터 스키마

### PersonMemory

```python
@dataclass
class PersonMemory:
    user_id: str              # 플랫폼 유저 ID
    platform: str             # 'twitter'
    screen_name: str          # @handle
    who_is_this: str          # 자연어 설명 (LLM 업데이트)
    tier: str                 # stranger → acquaintance → familiar → friend
    affinity: float           # -1.0 ~ 1.0
    memorable_moments: List   # 기억할 순간들
    latest_conversations: List # 최근 대화 (5개)
    first_met_at: datetime
    last_interaction_at: datetime
    updated_at: datetime
```

### ConversationRecord

```python
@dataclass
class ConversationRecord:
    conversation_id: str      # UUID
    person_id: str            # PersonMemory.user_id
    platform: str
    post_id: str              # 대화 시작점 트윗
    conversation_type: str    # 'my_post_reply' | 'their_post_reply' | 'dm'
    turn_count: int
    summary: str              # 대화 요약
    is_concluded: bool
    started_at: datetime
    last_turn_at: datetime
```

---

## 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│                    SocialEngineV2.step()                     │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │ random() < 0.6?               │
              ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │NotificationJourney│             │   FeedJourney   │
    └─────────────────┘             └─────────────────┘
              │                               │
              ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │get_all_notifications()│       │ _classify_posts()│
    └─────────────────┘             │   (rule-based)  │
              │                     └─────────────────┘
              ▼                               │
    ┌─────────────────┐                       ▼
    │_classify_notification()│      ┌─────────────────┐
    │  → scenario 선택     │       │ _select_best()  │
    └─────────────────┘             │   (1개 선택)    │
              │                     └─────────────────┘
              ▼                               │
    ┌─────────────────┐                       ▼
    │ Scenario.execute()│          ┌─────────────────┐
    │ ├─ _gather_context│          │ Scenario.execute│
    │ ├─ _judge (LLM)  │          │   (same flow)   │
    │ ├─ _execute_action│          └─────────────────┘
    │ └─ _update_memory│
    └─────────────────┘
              │
              ▼
    ┌─────────────────┐
    │  Twitter API    │
    │  (like/reply)   │
    └─────────────────┘
```

---

## 기존 시스템과의 관계

### 공존 가능
- `social/`는 기존 social 폴더를 대체
- `main.py`에서 선택적 사용 가능
- DB 테이블은 추가 (기존 테이블 유지)

### 공유하는 것
- `agent/memory/database.py` (MemoryDatabase)
- `agent/platforms/twitter/api/social.py` (Twitter API)
- `agent/platforms/twitter/modes/social/follow_engine.py` (FollowEngine)
- `core/llm.py` (LLM 클라이언트)
- `personas/*/` (페르소나 설정)

### 대체하는 것 (v2 사용 시)
- `agent/platforms/twitter/modes/social/reply_generator.py`
- `agent/core/behavior_engine.py` (일부 기능)
