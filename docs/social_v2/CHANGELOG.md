# Social Mode v2 변경 이력

## 2026-01-21: Initial Implementation

### 핵심 변경사항

**기존 Social Mode → Social Mode v2 리팩토링**

| 구분 | 기존 | v2 |
|------|------|-----|
| 진입점 | Feed 탐색 우선 | Notification 우선 (60%) |
| 아키텍처 | 단일 파이프라인 | Journey → Scenario → Action |
| LLM 호출 | 트윗당 1회 (8-9회/배치) | 선택된 1개만 (1-2회/배치) |
| 메모리 | 세션 기반 | PersonMemory + ConversationRecord |

### 추가된 파일

```
agent/platforms/twitter/modes/social_v2/
├── __init__.py
├── engine.py                    # SocialEngineV2 (통합 진입점)
├── journeys/
│   ├── __init__.py
│   ├── base.py                  # BaseJourney, JourneyResult
│   ├── notification.py          # NotificationJourney
│   └── feed.py                  # FeedJourney (HYBRID v1)
├── scenarios/
│   ├── __init__.py
│   ├── base.py                  # BaseScenario, ScenarioResult, ScenarioContext
│   ├── notification/
│   │   ├── __init__.py
│   │   ├── received_comment.py  # 내 글에 댓글
│   │   ├── mentioned.py         # 멘션
│   │   ├── quoted.py            # 인용
│   │   └── new_follower.py      # 새 팔로워
│   └── feed/
│       ├── __init__.py
│       ├── familiar_person.py   # 아는 사람 글
│       └── interesting_post.py  # 관심 주제 글
├── actions/
│   ├── __init__.py
│   ├── base.py                  # BaseAction, ActionResult
│   ├── like.py                  # LikeAction
│   ├── reply.py                 # ReplyAction
│   └── follow.py                # FollowAction
└── judgment/
    ├── __init__.py
    ├── engagement_judge.py      # LLM 기반 액션 결정
    └── reply_generator.py       # LLM 기반 답글 생성
```

### 수정된 파일

**agent/memory/database.py**
- `PersonMemory` dataclass 추가
- `ConversationRecord` dataclass 추가
- `person_memories` 테이블 추가
- `conversation_records` 테이블 추가
- CRUD 메서드 추가:
  - `get_or_create_person()`
  - `update_person()`
  - `get_or_create_conversation()`
  - `update_conversation()`

**agent/platforms/twitter/api/social.py**
- `NotificationData` TypedDict 추가
- `_classify_notification_type()` 함수 추가
- `get_all_notifications()` 함수 추가

### 테스트 결과

```
✓ 모든 import 성공
✓ FeedJourney 분류: familiar=0, interesting=1, others=2
✓ EngagementJudge: action='reply', confidence=0.9
✓ ReplyGenerator: 101자 자연스러운 한국어 답글
```

### Git 커밋

1. `Implement Social Mode v2 with Journey/Scenario/Action architecture`
   - 기본 구조 + DB 스키마 + API 추가

2. `Integrate LLM judgment and API calls into Social Mode v2`
   - EngagementJudge + ReplyGenerator
   - 실제 Twitter API 연동

---

## 향후 작업 (미구현)

- [ ] `main.py` bot loop에 SocialEngineV2 연결
- [ ] Unit tests 작성
- [ ] PostMemory 설계 (포스트별 반응 기록)
- [ ] PersonMemory `who_is_this` LLM 자동 업데이트
