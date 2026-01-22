# Virtual Agent (Dev)

Virtuals Protocol G.A.M.E SDK 기반 자율형 트위터 AI 에이전트. 사람다운 행동 패턴을 구현한 자율 소셜 에이전트.

## Core Flow

```
main.py (Entry)
    ↓
run_standalone_async() (USE_VIRTUAL_SDK 설정)
    ↓
ActivityScheduler (수면/활동 패턴 확인)
    ↓
session() 루프 (세션 기반, 30분-2시간 간격)
    ↓
Mode Selection (activity.yaml 가중치):
├─ Social (97%) → SocialEngine.session()
│   ├─ Phase 1: 알림 배치 처리 (3-8개)
│   │   └─ ReceivedComment/Mentioned/Quoted/NewFollower Scenario
│   ├─ Phase 2: 피드 배치 탐색 (5-15개 확인, 1-3개 반응)
│   │   └─ FamiliarPerson/InterestingPost Scenario
│   └─ Phase 3: 프로필 방문 (0-2개, 팔로잉 직접 확인)
│       └─ ProfileVisitJourney → FamiliarPerson/InterestingPost
├─ Casual (2%) → Trigger Engine + Post Generator
└─ Series (1%) → Planner → Writer → Studio → Archiver
```

### 세션 기반 구조 (v3)

사람 패턴 모사: **폰 켜서 알림 쭉 확인 → 피드 스크롤 → 폰 내려놓기 → 반복**

```
Session Start
├── Phase 1: 알림 처리 (3-8개, intra_delay 2-8초)
├── Phase 2: 피드 탐색 (5-15개 확인, 1-3개 반응)
├── Phase 3: 프로필 방문 (0-2개, 팔로잉 직접 확인)
Session End → 휴식 30분-2시간 → 다음 Session
```

**장점**: bursty한 활동 패턴으로 봇 탐지 회피, 더 자연스러운 소통

### Mode-Based Architecture (Platform-First)

| Mode | 목적 | 컴포넌트 | 실행 조건 |
|------|------|----------|----------|
| **Social** | 답글/멘션/관계 | `reply_generator.py`, `follow_engine.py` | scout/mentions 트리거 |
| **Casual** | 독립 포스팅 | `trigger_engine.py`, `post_generator.py` | 내부 상태 기반 발동 |
| **Series** | 콘텐츠 시리즈 | `engine.py`, `planner.py`, `writer.py`, `studio/` | 스케줄링된 포스팅 |
| **Learning** | 트렌드/지식 습득 | `trend_learner.py` | 주기적 트렌드 수집 |

### Social Engine (Session-Based v3)

세션 기반 시나리오 아키텍처:

```
SocialEngine.session()
    ↓
Phase 1: 알림 배치 (3-8개)
├─ 알림 가져오기 → 이미 처리된 알림 필터링
├─ 시나리오 매칭 → 실행 (intra_delay 2-8초)
│   ├─ ReceivedCommentScenario (내 글에 댓글)
│   ├─ MentionedScenario (멘션)
│   ├─ QuotedScenario (인용)
│   └─ NewFollowerScenario (팔로우)
└─ 처리 완료 기록 (processed_notifications)
    ↓
Phase 2: 피드 배치 (5-15개 확인, 1-3개 반응)
├─ Rule-based 분류 (LLM 0회)
├─ 1개씩 LLM 판단 (최대 react_count개)
│   ├─ FamiliarPersonScenario (아는 사람 글)
│   └─ InterestingPostScenario (관심 키워드 매칭)
└─ 스크롤 딜레이 (1-4초)
    ↓
Phase 3: 프로필 방문 (0-2개)
├─ 팔로잉 목록에서 대상 선택 (familiar_first 또는 random)
├─ 대상 프로필의 최근 글 가져오기
└─ FamiliarPerson/InterestingPost 시나리오로 상호작용
```

| 컴포넌트 | 위치 | 역할 |
|---------|------|------|
| SocialEngineV2 | `modes/social/engine.py` | 통합 진입점, Journey 오케스트레이션 |
| NotificationJourney | `modes/social/journeys/notification.py` | 알림 기반 시나리오 선택 |
| FeedJourney | `modes/social/journeys/feed.py` | 피드 분류 + 우선순위 선택 |
| ProfileVisitJourney | `modes/social/journeys/profile_visit.py` | 팔로잉 프로필 방문 + 상호작용 |
| EngagementJudge | `modes/social/judgment/engagement_judge.py` | LLM 기반 행동 판단 |
| ReplyGenerator | `modes/social/judgment/reply_generator.py` | 답글 생성 |
| PersonMemory | `agent/memory/database.py` | 사람 기억 (tier/affinity 기반) |

**핵심 차이 (Legacy vs V2)**:
| 항목 | Legacy | V2 |
|------|--------|-----|
| LLM 호출 | 트윗당 1회 (8-9회) | 선택된 1개만 (1-2회) |
| 진입점 | Feed 우선 | Notification 우선 (60%) |
| 사람 기억 | 세션 기반 | PersonMemory (DB, tier 승격) |
| 팔로우 | 별도 로직 | 시나리오 내 통합 |

## 4-Layer Intelligence

| Layer | 소스 | 용도 |
|-------|------|------|
| Core | `personas/*/identity.yaml` | 페르소나 본질 (요리사 정체성) |
| Curiosity | `agent/memory/session.py` | 최근 관심사 (자동 학습/감쇠, 소스 추적) |
| Knowledge | `agent/knowledge/knowledge_base.py` | 트렌드 컨텍스트 (요약/관련도/내 관점) |
| Trends | `platforms/twitter/trends.py` | 실시간 트위터 트렌드 → Knowledge로 학습

## Folder Structure

```
virtual/
├── _archive/                    # 레거시/제외된 코드
│   ├── actions/                # 오래된 플랫폼 구현
│   └── docs/                   # 오래된 문서
├── actions/                    # 현재 액션 (market_data.py만)
├── agent/                      # 코어 에이전트 로직
│   ├── bot.py                  # 메인 진입점, SocialAgent 클래스
│   ├── core/                   # 플랫폼 독립 로직 (9개 모듈)
│   │   ├── activity_scheduler.py # 수면/휴식 패턴
│   │   ├── base_generator.py   # 콘텐츠 생성 베이스 클래스
│   │   ├── behavior_engine.py  # 확률 기반 행동 판단 + HumanLikeController
│   │   ├── follow_engine.py    # 점수 기반 팔로우 판단 + 지연 큐
│   │   ├── interaction_intelligence.py # 트윗 분석 + ResponseType 결정
│   │   ├── mode_manager.py     # 모드 시스템 (normal/test/aggressive)
│   │   ├── text_utils.py       # 텍스트 처리 유틸리티
│   │   └── topic_selector.py   # 가중치 기반 토픽 선택
│   ├── memory/                 # 메모리 시스템 (8개 모듈)
│   │   ├── consolidator.py     # 메모리 정리
│   │   ├── database.py         # SQLite 장기 메모리
│   │   ├── factory.py          # 메모리 DI 팩토리
│   │   ├── inspiration_pool.py # 영감 풀
│   │   ├── session.py          # 세션 메모리 (interactions, likes, curiosity)
│   │   ├── tier_manager.py     # 티어 관리 + 품질 경쟁
│   │   └── vector_store.py     # ChromaDB 벡터 검색
│   ├── knowledge/              # 세상 지식
│   │   └── knowledge_base.py   # 트렌드/키워드 컨텍스트 학습
│   ├── persona/                # 페르소나 관련 (2개 모듈)
│   │   ├── persona_loader.py   # YAML 로딩 (중앙 진입점)
│   │   └── relationship_manager.py # 유저 관계 추적
│   └── platforms/              # 플랫폼별 로직
│       ├── interface.py        # 플랫폼 어댑터 인터페이스
│       └── twitter/            # Twitter 전용 모듈
│           ├── adapter.py      # TwitterAdapter (platforms/twitter/social.py 래퍼)
│           ├── formatter.py    # 트윗 텍스트 포매팅
│           ├── learning/       # 1개 트렌드 학습기
│           │   └── trend_learner.py
│           └── modes/          # 모드 기반 아키텍처
│               ├── casual/     # 2개 캐주얼 모듈
│               │   ├── trigger_engine.py
│               │   └── post_generator.py
│               ├── series/     # 시리즈 모듈
│               │   ├── engine.py
│               │   ├── planner.py
│               │   ├── writer.py
│               │   ├── archiver.py
│               │   ├── reviewer.py
│               │   ├── studio/
│               │   │   ├── generator.py
│               │   │   └── critic.py
│               │   └── adapters/
│               │       └── twitter.py  # 트위터 시리즈 포스팅 어댑터
│               └── social/     # 4개 소셜 모듈
│                   ├── reply_generator.py
│                   ├── behavior_engine.py
│                   ├── follow_engine.py
│                   └── reviewer.py

config/                         # 설정 관리
├── active_persona.yaml          # 현재 활성 페르소나 지정
└── settings.py                  # 종합 설정 + 환경변수

core/                           # 1개 LLM 클라이언트 모듈
└── llm.py                      # 멀티 LLM 클라이언트

data/                           # 런타임 데이터 (페르소나별)

personas/                       # 페르소나 설정 (계층 구조)
├── _template/                  # 페르소나 템플릿
└── chef_choi/                  # 활성 페르소나
    ├── identity.yaml            # 핵심 정체성 (이름, 도메인, 성격)
    ├── speech_style.yaml        # 말투 예시 기반 (간소화됨)
    ├── behavior.yaml            # 행동 확률 모델 & 휴먼라이크 설정
    ├── core_relationships.yaml  # 핵심 관계
    ├── prompt.txt              # 시스템 프롬프트
    └── platforms/              # 플랫폼별 분리
        └── twitter/
            ├── config.yaml      # 플랫폼 제약 & 문자 규칙
            ├── activity.yaml    # 세션 설정 + 모드 가중치 + human-like
            └── modes/          # 모드 통합 (config+style)
                ├── casual/     # config.yaml + style.yaml
                ├── series/     # config.yaml + style.yaml + studio.yaml
                └── social/     # config.yaml + style.yaml + behavior.yaml

platforms/                     # Twitter API 래퍼 (agent/platforms/twitter/adapter.py가 사용)
└── twitter/
    ├── social.py              # Twikit 기반 Twitter API
    └── trends.py              # 트렌드 수집

script/                        # 유틸리티 스크립트
scripts/                       # 메인 스크립트 (백업, 마이그레이션)
tests/                         # 테스트 파일
```

## Key Components

| 파일 | 역할 |
|------|------|
| `agent/bot.py` | SocialAgent 클래스, 전체 워크플로우 |
| `agent/core/base_generator.py` | 콘텐츠 생성 베이스 클래스 |
| `agent/core/behavior_engine.py` | BehaviorEngine + HumanLikeController (워밍업/지연/버스트 방지) |
| `agent/core/interaction_intelligence.py` | LLM 기반 트윗 분석/판단 + ResponseType 결정 |
| `agent/core/mode_manager.py` | 모드 시스템 (normal/test/aggressive) + 세션 간격 관리 |
| `agent/core/activity_scheduler.py` | 사람다운 휴식 패턴 (수면/시간대별 활동/랜덤 휴식/오프데이) |
| `agent/core/topic_selector.py` | 가중치 기반 토픽 선택 (core/time/curiosity/trends/inspiration) |
| `agent/core/follow_engine.py` | 점수 기반 팔로우 판단 + 지연 큐 |
| `agent/core/text_utils.py` | 텍스트 처리 유틸리티 |
| `agent/memory/session.py` | 세션 메모리 - interactions, facts, curiosity |
| `agent/memory/database.py` | SQLite 장기 메모리 (Episode, Inspiration, CoreMemory) |
| `agent/memory/factory.py` | 메모리 DI 팩토리 (페르소나별 메모리 인스턴스) |
| `agent/knowledge/knowledge_base.py` | 트렌드/키워드 컨텍스트 학습 (요약, 관련도, 내 관점) |
| `agent/persona/persona_loader.py` | YAML 기반 페르소나 로딩 (중앙 로딩 지점) |
| `agent/persona/relationship_manager.py` | 유저 관계 추적 (사전정의 + 동적) |
| `agent/platforms/interface.py` | 플랫폼 어댑터 인터페이스 (SocialPlatformAdapter) |
| `agent/platforms/twitter/adapter.py` | TwitterAdapter - platforms/twitter/social.py 래퍼 |
| `platforms/twitter/social.py` | Twikit 기반 Twitter API |
| `platforms/twitter/trends.py` | 트렌드 수집 + Knowledge 자동 학습 |
| `core/llm.py` | 멀티 LLM 클라이언트 (Gemini, OpenAI, Anthropic) |

### Mode-Based Components

| Mode | 컴포넌트 | 역할 |
|------|----------|------|
| **Casual** | `agent/platforms/twitter/modes/casual/trigger_engine.py` | 내부 상태 기반 포스팅 트리거 (flash/mood_burst/random_recall) |
| **Casual** | `agent/platforms/twitter/modes/casual/post_generator.py` | 다양성 검증 + 반복 방지 독립 포스팅 생성 |
| **Social** | `agent/platforms/twitter/modes/social/reply_generator.py` | ResponseType 기반 답글 생성 (QUIP/SHORT/NORMAL/LONG/PERSONAL) |
| **Social** | `agent/platforms/twitter/modes/social/behavior_engine.py` | 모드 인식 행동 엔진 (향상된 관계 판단) |
| **Social** | `agent/platforms/twitter/modes/social/follow_engine.py` | 모드별 팔로우 로직 |
| **Social** | `agent/platforms/twitter/modes/social/reviewer.py` | 답글 콘텐츠 리뷰 |
| **Series** | `agent/platforms/twitter/modes/series/engine.py` | 시리즈 콘텐츠 오케스트레이터 |
| **Series** | `agent/platforms/twitter/modes/series/planner.py` | 토픽 큐레이션 + 스케줄링 |
| **Series** | `agent/platforms/twitter/modes/series/writer.py` | 시리즈 전용 콘텐츠 생성 |
| **Series** | `agent/platforms/twitter/modes/series/studio/` | 이미지 생성 + AI 비평 + 선택 |
| **Series** | `agent/platforms/twitter/modes/series/archiver.py` | 시리즈 에피소드 기록 관리 |
| **Series** | `agent/platforms/twitter/modes/series/reviewer.py` | 시리즈 콘텐츠 리뷰 |
| **Series** | `agent/platforms/twitter/modes/series/adapters/twitter.py` | 트위터 시리즈 포스팅 어댑터 |
| **Learning** | `agent/platforms/twitter/learning/trend_learner.py` | 트렌드 키워드 컨텍스트 수집 |

## Behavior Engine

`agent/core/behavior_engine.py` + `personas/chef_choi/behavior.yaml`

### BehaviorEngine (가산 확률 모델)
- **가산 확률 모델**: 기본 확률 + 상황별 가산점으로 행동 확률 계산
- **기분 변동**: 시간대/최근 상호작용/랜덤 요소
- **현타 시스템**: 같은 글에 댓글 많이 달면 자제
- **집착 주제**: 관심 주제면 가산점 (obsession +0.30)
- **행동별 반영 비율**: like(100%), repost(80%), comment(60%)

### HumanLikeController (봇 탐지 회피)
- **워밍업**: 처음 N스텝 동안 읽기만 (액션 없음)
- **액션 지연**: like 후 2-5초, comment 후 5-15초, post 후 30-120초
- **버스트 방지**: 연속 3회 액션 후 쿨다운

### 튜닝 가능 설정 (behavior.yaml)
```yaml
# Behavior Engine V2: 가산 확률 모델 (Additive Model)
probability_model:
  base_probability: 0.50       # 기본 확률 (50%)

  # 행동별 반영 비율
  action_ratios:
    like: 1.0
    repost: 0.8
    comment: 0.6

  # 상황별 가산점 (Modifiers)
  modifiers:
    praise: 0.15
    criticism: -0.20
    obsession: 0.30
    stranger: -0.10
    introversion: -0.10
    aggressive_mode: 0.30

# 콘텐츠 리뷰 레이어 설정
content_review:
  enabled: true
  fix_excessive_patterns: true
  max_pattern_occurrences: 1

# 팔로우 행동 설정
follow_behavior:
  enabled: true
  daily_limit: 100
  base_probability: 0.5
  score_threshold: 40
  delay:
    min: 30
    max: 300
  exclude:
    no_profile_image: true
    no_bio: true

# Human-like 행동 패턴 (봇 탐지 회피)
human_like:
  warmup:
    enabled: true
    steps: 5
  action_delays:
    after_like: [2, 5]
    after_comment: [5, 15]
    after_post: [30, 120]
  burst_prevention:
    enabled: true
    max_consecutive_actions: 3
    cooldown_after_burst: 60
```

## Tweet Selection & Action Decision

`agent/bot.py` + `agent/core/behavior_engine.py` + `platforms/twitter/social.py`

### 트윗 선택 (Score-based Selection)

검색된 트윗 중 가장 적합한 트윗을 점수 기반으로 선택:

```
search_tweets(8개) → 전체 perceive → 점수 계산 → 최고 점수 선택
```

**점수 계산 (`_calculate_tweet_score`)**:
| 요소 | 가중치 | 설명 |
|------|--------|------|
| 관련도 | 50% | `perception.relevance_to_cooking` (0.0~1.0) |
| 인기도 | 30% | `(likes + retweets*2) / 50` 정규화 |
| 복잡도 | 20% | complex=0.2, moderate=0.1, simple=0 |

### 행동 결정 (Context-aware Action Decision)

`decide_actions(perception, tweet)`: 관련도/인기도 기반 확률 조정

**확률 조정 공식**:
```python
relevance_factor = 0.3 + (relevance * 0.7)  # 0.3 ~ 1.0
popularity_factor = 0.5 + (likes + retweets*2) / 40  # 0.5 ~ 1.0

like_prob = base * relevance_factor
repost_prob = base * relevance_factor * popularity_factor
comment_prob = base * relevance_factor
```

**Repost 제한**:
- `relevance < 0.4` → repost 확률 0% (최소 관련도 임계값)

### Engagement 데이터 수집

`platforms/twitter/social.py`의 `TweetData` 구조:
```python
{
    "id": str,
    "user": str,
    "text": str,
    "created_at": str,
    "engagement": {
        "favorite_count": int,
        "retweet_count": int,
        "reply_count": int,
        "quote_count": int,
        "view_count": int | None,
        "bookmark_count": int
    }
}
```

확장성: 추후 Twitter API v2 전환 시 `_search_tweets_twikit`만 교체

## Persona System

### 폴더 구조
```
config/active_persona.yaml              # 현재 활성 페르소나 지정
personas/                               # 페르소나 설정 (계층 구조)
├── _template/                          # 페르소나 템플릿
└── chef_choi/                          # 활성 페르소나
    ├── identity.yaml                   # 정체성 + 행동 확률 모델
    ├── speech_style.yaml               # 말투 + 콘텐츠 검증 설정
    ├── mood.yaml                       # 기분 & 스케줄
    ├── core_relationships.yaml         # 핵심 관계
    ├── prompt.txt                      # 시스템 프롬프트
    └── platforms/
        └── twitter/
            ├── config.yaml             # 플랫폼 제약 (글자수, 금지문자)
            ├── activity.yaml           # 모드 가중치 + human-like + 스텝 간격
            └── modes/
                ├── casual/             # config.yaml + style.yaml
                ├── series/             # config.yaml + style.yaml + studio.yaml
                └── social/             # config.yaml + style.yaml (통합)
```

### 파일별 역할

| 파일 | 역할 | 새 페르소나 시 수정 필요 |
|------|------|------------------------|
| `identity.yaml` | 이름, 직업, 도메인, 키워드 | ✅ 필수 |
| `speech_style.yaml` | 말투 예시, 피해야 할 표현 | ✅ 필수 |
| `prompt.txt` | LLM 시스템 프롬프트 | ✅ 필수 |
| `core_relationships.yaml` | 특정 유저와의 관계 정의 | 선택 |
| `platforms/twitter/activity.yaml` | 세션 설정, 모드 가중치, human-like | ✅ 성격별 조정 |
| `platforms/twitter/modes/social/config.yaml` | quip_pool, follow, interaction_patterns | ✅ 도메인별 수정 |
| `platforms/twitter/modes/social/style.yaml` | 답글 말투, 전문가 회피 문구 | ✅ 도메인별 수정 |
| `platforms/twitter/modes/series/studio.yaml` | 이미지 생성 스타일 | ✅ 도메인별 수정 |

### 설정 계층 (Config Hierarchy)

```
identity.yaml (Base)
    └── core_keywords                  → SocialEngine (FeedJourney 분류)

speech_style.yaml (Speech - 예시 기반)
    └── personality_brief              → LLM 프롬프트에 성격 한 줄
    └── speech_examples                → LLM 참고용 말투 예시
    └── avoid                          → 피해야 할 표현

platforms/twitter/activity.yaml (Activity - v3 세션 기반)
    └── mode_weights                   → 모드 선택 (social/casual/series)
    └── session.interval               → 세션 간 휴식 (30분-2시간)
    └── session.notification.count     → 세션당 알림 처리 개수
    └── session.feed.browse_count      → 세션당 피드 확인 개수
    └── session.intra_delay            → 세션 내 작업 간 딜레이
    └── human_like                     → 읽기/생각/타이핑/전환 딜레이
    └── activity_schedule              → 수면/휴식 패턴

platforms/twitter/modes/social/
    ├── config.yaml (통합)
    │   └── response_strategy          → V2 ReplyGenerator (응답 타입 결정)
    │   └── quip_pool                  → V2 ReplyGenerator (QUIP 반응)
    │   └── interaction_patterns       → same_user, same_post 제한
    │   └── behavioral_rules           → 피로도, 집착 주제
    │   └── follow_behavior            → FollowEngine
    └── style.yaml
        └── constraints                → ReplyGenerator (전문가 회피)
        └── response_types             → ReplyGenerator (길이/톤)
```

### 페르소나 이식성
**페르소나 폴더 복사 = 완전 독립 에이전트**

```bash
# 새 페르소나 생성
cp -r personas/chef_choi personas/new_persona

# 필수 수정 파일
# 1. identity.yaml - 이름, 직업, 도메인, 키워드
# 2. speech_style.yaml - 말투 패턴, 시그니처
# 3. prompt.txt - 시스템 프롬프트
# 4. platforms/twitter/modes/social/config.yaml - quip_pool (도메인 반응)
# 5. platforms/twitter/modes/social/style.yaml - avoid_expert_phrases

# active_persona.yaml 수정
echo "active: new_persona" > config/active_persona.yaml

# 또는 환경변수로 실행
PERSONA_NAME=new_persona python main.py
```

### 새 페르소나 체크리스트

1. **identity.yaml**
   - [ ] `name`, `occupation`, `nickname` 변경
   - [ ] `domain.name`, `domain.keywords` 변경
   - [ ] `core_keywords` 변경
   - [ ] `agent_goal`, `agent_description` 변경

2. **speech_style.yaml** (예시 기반)
   - [ ] `personality_brief` 변경 (성격 한 줄)
   - [ ] `tone` 변경 (말투 톤)
   - [ ] `speech_examples` 변경 (실제 말투 예시 6-10개)
   - [ ] `avoid` 변경 (피해야 할 전문가 표현)

3. **prompt.txt**
   - [ ] 전체 다시 작성

4. **social/config.yaml**
   - [ ] `quip_pool` 변경 (도메인 관련 짧은 반응)

5. **social/style.yaml**
   - [ ] `constraints.avoid_expert_phrases` 변경 ("요리사로서..." → "개발자로서...")
   - [ ] `review.speech_examples` 변경

### speech_style.yaml (예시 기반 - v3)
```yaml
# 성격 한 줄
personality_brief: "내성적이지만 요리 얘기엔 눈 반짝. 말 아끼지만 진심 담김."

# 톤 설명
tone: "친근하지만 과하지 않게. 전문가 티 안 내고 자연스럽게."

# 실제 말투 예시 (LLM 참고용)
speech_examples:
  - "음... 그건 좀 다르게 봐야 할 것 같아요"
  - "아, 그거 저도 해봤는데 괜찮더라고요"
  - "소금 살짝 더 넣으면 완전 달라져요"

# 피해야 할 표현
avoid:
  - "요리사로서 말씀드리면"
  - "전문가 입장에서"

# 문장 시작/종결 풀 (랜덤 선택용)
opener_pool: ["음...", "어...", "그게...", "아 그러고보니"]
closer_pool: ["~거든요", "~인 거죠", "~같아요", "~인데..."]
```

**핵심 변경**: 규칙 기반(pattern_registry) → 예시 기반(speech_examples)
- 시그니처 반복 문제 해결
- LLM이 예시 참고해서 자연스럽게 변형

### 모드별 설정 예시

#### Activity Config (`platforms/twitter/activity.yaml` - 세션 기반 v3)
```yaml
# 모드 가중치
mode_weights:
  social: 0.97
  casual: 0.02
  series: 0.01

# 세션 기반 활동
session:
  interval: [1800, 7200]      # 세션 간 휴식 (30분-2시간)

  notification:
    count: [3, 8]             # 세션당 알림 처리 개수
    priority_boost:
      mention: 1.5
      reply: 1.3

  feed:
    browse_count: [5, 15]     # 확인할 피드 개수
    react_count: [1, 3]       # 반응할 개수
    familiar_first: true

  intra_delay: [2, 8]         # 세션 내 작업 간 딜레이 (초)
  warmup_sessions: 2          # 워밍업 세션 (읽기만)

# 수면/휴식 패턴
activity_schedule:
  sleep_pattern:
    base_sleep_start: 1
    base_wake_time: 7
  hourly_activity:
    "07-09": 0.3
    "18-22": 1.0
```

#### Casual Mode Style (`platforms/twitter/modes/casual/style.yaml`)
```yaml
casual_style:
  tone: "스스로 생각하며 혼잣말처럼"
  length_range: { min: 40, max: 200 }
  triggers:
    flash:
      enabled: true
      impact_threshold: 0.9
    mood_burst:
      enabled: true
      impact_threshold: 0.8
```

#### Series Mode Config (`personas/chef_choi/platforms/twitter/modes/series/config.yaml`)
```yaml
series:
  - id: "world_braised"
    name: "세계의 조림"
    description: "세계 각국의 독특한 조림 요리와 그 이야기를 소개"
    frequency: "2days"
    time_variance: "2h"
    curation:
      enabled: true
      search_query: "unique braised dishes around the world traditional stew recipes history"
      prompt: "세계의 독특한 조림(Braised) 요리를 찾아주세요..."
      validation_criteria: "Is this dish prepared using a 'Braising' or 'Jorim' technique?"
      count_per_fetch: 5

  - id: "ingredient_lab"
    name: "재료 연구소"
    description: "한 가지 식재료를 깊이 있게 탐구"
    frequency: "3days"
    curation:
      enabled: true
      search_query: "seasonal food ingredients science cooking tips"
      count_per_fetch: 3
```

#### Social Mode Config (`personas/chef_choi/platforms/twitter/modes/social/config.yaml`)
```yaml
response_strategy:
  base_probabilities:
    quip: 0.20        # 초짧은 패턴 반응 (1-15자)
    short: 0.40       # 짧은 반응 (15-50자)
    normal: 0.30      # 보통 (50-100자)
    long: 0.05        # 긴 TMI (80-140자, 전문 분야)
    personal: 0.05    # 개인 감상 (전문성 없이)

  tweet_length_modifiers:
    short_tweet: { threshold: 30, probabilities: { quip: 0.50, short: 0.40, normal: 0.10 } }
    medium_tweet: { threshold: 80, probabilities: { quip: 0.20, short: 0.40, normal: 0.30, long: 0.05, personal: 0.05 } }
    long_tweet: { probabilities: { quip: 0.10, short: 0.20, normal: 0.40, long: 0.20, personal: 0.10 } }

quip_pool:
  agreement: ["그렇죠", "맞아요", "인정"]
  impressed: ["조리겠습니다", "풍미가...", "오...", "텍스처..."]
  casual: ["음...", "어...", "그게..."]
  food_related: ["들기름 한바퀴", "이건 조려야죠", "소금 넉넉히"]
```

## External Dependencies

| 라이브러리 | 용도 | 주의사항 |
|-----------|------|---------|
| `game-sdk` | Virtuals Protocol G.A.M.E SDK | 429 rate limit 빈번, retry 로직 필수 |
| `twikit` | Twitter 비공식 SDK | 쿠키 인증 필요 (auth_token, ct0) |
| `google-genai` | Gemini LLM | API 키 필수 |
| `chromadb>=1.0.0` | 벡터 저장소 | **1.0.0+** 필수 (DB 마이그레이션 호환) |
| `python-dotenv` | 환경변수 관리 | .env 파일 로딩 |
| `requests` | HTTP 클라이언트 | API 호출용 |
| `tweepy` | Twitter 공식 SDK (예비) | 현재는 twikit 사용 |

### 의존성 변화
- **실제**: 8개의 최소한의 의존성 (경량화)
- **문서상**: 더 많은 라이브러리가 문서화됨
- **핵심**: `game-sdk`, `twikit`, `google-genai`, `chromadb`가 주요 의존성 |

## DO NOT TOUCH

| 파일/폴더 | 이유 |
|----------|------|
| `.env` | API 키, Twitter 인증 정보 |
| `chrome_data/` | Twitter 세션 데이터 |
| `agent_memory.json` | 런타임 메모리 (interactions, relationships) |
| `data/posted_content.txt` | 게시 로그 (fallback) |

## Mode System

### 세션 기반 Mode Architecture (v3)

`agent/core/mode_manager.py` + 환경변수 `AGENT_MODE`

### Execution Control Modes (normal/test/aggressive)

| Mode | 세션 간격 | 워밍업 세션 | 수면 | 휴식 |
|------|----------|-----------|------|------|
| **normal** | 30분-2시간 | 2 | O | O |
| **test** | 1-3분 | 0 | X | X |
| **aggressive** | 15-45초 | 0 | X | X |

| Mode | Like | Repost | Comment |
|------|------|--------|---------|
| **normal** | 페르소나 값 | 페르소나 값 | 페르소나 값 |
| **test** | 45% | 45% | 12% |
| **aggressive** | 60% | 60% | 18% |

### Content Generation Modes

#### 1. Casual Mode (독립 포스팅)
**구성**: `trigger_engine.py`, `post_generator.py`

**트리거 타입**:
- `flash`: impact_threshold=0.9 (매우 강렬한 경험)
- `flash_reinforced`: impact_threshold=0.8 (관심 재강화)
- `mood_burst`: impact_threshold=0.8 (기분 좋은 순간)
- `random_recall`: impact_threshold=0.0 (갑작스러운 회상)

**핵심 기능**:
- **다양성 검증**: 최근 포스팅 분석으로 반복 방지
- **반복 제어**: 금지된 주제/표현 필터링
- **길이 제약**: 설정 가능한 최소/최대 길이

#### 2. Social Mode (답글/멘션)
**구성**: `reply_generator.py`, `behavior_engine.py`

**ResponseType 분기**:
| Type | 조건 | LLM 호출 | 길이 |
|------|------|----------|------|
| **QUIP** | complexity=simple + quip_category!=none | ❌ 패턴 풀 | 1-15자 |
| **SHORT** | complexity=simple + quip_category=none | ✅ 최소 | 15-50자 |
| **NORMAL** | complexity=moderate | ✅ 표준 | 50-100자 |
| **LONG** | cooking_rel≥0.7 + complex | ✅ 상세 | 80-140자 |
| **PERSONAL** | 비전문가 회고 | ✅ 개인적 | 30-80자 |

**QUIP Pool 예시**:
```yaml
quip_pool:
  agreement: ["인정", "ㄹㅇ", "맞음"]
  impressed: ["조리겠습니다", "이건 뭉근하게..."]
  casual: ["ㅋㅋ", "ㅎㅎ", "음..."]
  food_related: ["들기름 한바퀴", "이건 조려야됨"]
```

#### 3. Series Mode (콘텐츠 시리즈)
**구성**: `engine.py`, `planner.py`, `writer.py`, `studio/`, `archiver.py`

**워크플로우**:
1. **Planning** → 토픽 큐레이션 + 스케줄링
2. **Writing** → 시리즈 전용 프롬프트 + 톤
3. **Studio** → 이미지 생성 (4개 후보) → AI 비평 → 선택
4. **Archiving** → 에피소드 전체 기록 + 메타데이터

**시리즈 설정 예시**:
```yaml
series:
  - id: "world_braised"
    name: "세계의 조림"
    frequency: "2days"
    time_variance: "2h"
    curation:
      enabled: true
      search_query: "unique braised dishes around the world"
```

#### 4. Learning Mode (트렌드 학습)
**구성**: `trend_learner.py`

**기능**: 가벼운 트렌드 컨텍스트 수집 → `knowledge_base.py`로 전달

### Mode Integration Flow

```python
# Main Loop (main.py - async)
async def run_standalone_async():
    while True:
        # 수면/휴식 체크
        if mode_manager.config.sleep_enabled:
            is_active, state, _ = activity_scheduler.is_active_now()
            if not is_active:
                await asyncio.sleep(sleep_seconds)
                continue

        # 모드 선택 (activity.yaml의 mode_weights)
        roll = random.random()
        if roll < mode_weights['social']:
            result = await social_agent.run_social_session()  # 세션 실행
        elif roll < mode_weights['social'] + mode_weights['casual']:
            social_agent.post_tweet_executable()
        else:
            social_agent.run_series_step()

        # 세션 간 휴식
        session_min, session_max = mode_manager.get_session_interval()
        await asyncio.sleep(random.randint(session_min, session_max))
```

### 동작 방식
- **normal**: 페르소나 `activity.yaml`의 세션 설정 사용 (프로덕션용)
- **test/aggressive**: 짧은 세션 간격으로 오버라이드 (개발용)
- 226 에러 발생 시 aggressive → normal 자동 전환
- 연속 3회 에러 시 normal로 전환 + 5분 정지

### 페르소나 이식성
```
normal 모드 = 페르소나 100% 존중
├── 세션: activity.yaml의 session 설정
├── 성격: identity.yaml의 personality
└── 스타일: speech_style.yaml (예시 기반)

→ 페르소나 폴더 복사 + active_persona.yaml 변경 = 완전 교체
```

### 사용 예시
```bash
# normal 모드 (기본, 30분-2시간 간격)
AGENT_MODE=normal python main.py

# test 모드 (1-3분 간격)
AGENT_MODE=test python main.py

# aggressive 모드 (15-45초 간격, 봇 감지 위험)
AGENT_MODE=aggressive python main.py
```

## Run

```bash
source .venv/bin/activate
python main.py

# 환경변수로 SDK 모드 선택
USE_VIRTUAL_SDK=true python main.py   # SDK 모드
USE_VIRTUAL_SDK=false python main.py  # Standalone 모드 (기본)

# 모드 조합 예시
AGENT_MODE=test USE_VIRTUAL_SDK=false python main.py
```

## Coding Rules

### 주석 스타일
- **모듈 docstring**: 한국어 + 영어 병기
  ```python
  """
  Behavior Engine
  확률 기반 판단 / 기분 변동 / 현타 시스템
  Probabilistic decision-making with mood & regret
  """
  ```
- **인라인 주석**: 한국어로 짧게 (`# 시간대 영향`)
- **메서드 docstring**: 필요시 한국어/영어 병기

### 코드 스타일
- AI가 쓴 것 같은 과도한 주석 금지
- 뻔한 코드에 주석 달지 않음
- 변수명/함수명으로 의도 표현

### 금지 패턴
```python
# BAD - 뻔한 주석
i = 0  # Initialize counter to zero

# GOOD - 필요한 주석만
i = 0  # 재시도 횟수
```

## Content Generation

콘텐츠 생성은 모드별로 분리:
- `agent/core/base_generator.py` - 공통 생성 베이스 클래스
- `agent/platforms/twitter/modes/social/reply_generator.py` - 답글 생성
- `agent/platforms/twitter/modes/casual/post_generator.py` - 독립 포스팅 생성

### ResponseType 분기 시스템

```
트윗 분석 (perceive)
    ↓
complexity + quip_category 판단
    ↓
response_type 결정
    ↓
┌─ QUIP   → LLM 없이 quip_pool에서 선택 (1-15자)
├─ SHORT  → 간단 프롬프트 (15-50자)
├─ NORMAL → 표준 chat 모드 (50-100자)
└─ LONG   → 요리 TMI 모드 (80-140자)
```

### ResponseType 결정 기준

| Type | 조건 | LLM 호출 |
|------|------|----------|
| **QUIP** | complexity=simple + quip_category!=none | ❌ 패턴 풀 |
| **SHORT** | complexity=simple + quip_category=none | ✅ 최소 |
| **NORMAL** | complexity=moderate | ✅ 표준 |
| **LONG** | cooking_rel≥0.7 + complex, 또는 요리 질문 | ✅ 상세 |

### QUIP Pool (social/config.yaml)
```yaml
quip_pool:
  agreement: ["인정", "ㄹㅇ", "맞음"]
  impressed: ["조리겠습니다", "이건 뭉근하게...", "풍미가..."]
  casual: ["ㅋㅋ", "ㅎㅎ", "음..."]
  food_related: ["들기름 한바퀴", "이건 조려야됨"]
  skeptical: ["음... 글쎄요", "그건 좀..."]
  simple_answer: ["네", "아뇨"]
```

### 검증 레이어
1. **금지 문자 검증**: 한자/일본어 포함 시 재생성 (최대 3회)
2. **Twitter 글자수 검증**: 한글 가중치 적용 (한글 1자 = 2 가중치, 280 제한)
3. **LLM 리뷰 레이어**: Pattern Tracker 연동
   - 과도한 말투 패턴 교정 (`~거든요` 연속 사용 등)
   - 페르소나 보존 (min_per_post, is_core_trait)

### Post 모드 (독립 포스팅)
| Mode | 용도 | 길이 | 톤 |
|------|------|------|-----|
| **chat** | 답글/대화 | 15-100자 | 친근하고 도움주는 |
| **post** | 독립 포스팅 | 20-120자 | 짧고 임팩트 |

## Activity Scheduler

`agent/core/activity_scheduler.py` - 사람다운 휴식 패턴

### 기능
- **수면 시간**: 매일 다른 취침/기상 시간 (variance 적용)
- **주말 보정**: 주말엔 늦게 자고 늦게 일어남
- **새벽 폰 체크**: 8% 확률로 새벽 2-5시 중 깨어남
- **시간대별 활동**: 아침(0.3) → 오후(0.8) → 저녁(1.0) 가변 강도
- **랜덤 휴식**: 15% 확률로 30-180분 휴식
- **오프 데이**: 10% 확률로 하루 쉼

### 활동 상태
| State | 의미 | 다음 활동 시간 |
|-------|------|---------------|
| ACTIVE | 활동 중 | - |
| SLEEPING | 수면 중 | 기상 시간 |
| BREAK | 휴식 중 | 휴식 종료 시간 |
| OFF_DAY | 오프 데이 | 다음날 0시 |

## Memory System

`agent/memory/` - 품질 경쟁 기반 동적 메모리

### 메모리 팩토리 (DI)
**파일**: `agent/memory/factory.py`

`MemoryFactory`로 페르소나별 메모리 인스턴스 생성:
```python
memory_db = MemoryFactory.get_memory_db(persona_id)    # SQLite
vector_store = MemoryFactory.get_vector_store(persona_id)  # ChromaDB
```

### 단기 기억 (Operational)
**파일**: `agent/memory/session.py` → `agent_memory.json`

| 데이터 | 보관 한계 | 용도 |
|--------|----------|------|
| interactions | 최근 100건 | 답글 기록 (중복 방지) |
| likes | 최근 500건 | 좋아요 기록 |
| curiosity | 감쇠 적용 | 관심 키워드 카운트 |

### 장기 기억 (Semantic)
**파일**: `agent/memory/` → `data/personas/{id}/db/` (SQLite) + `data/personas/{id}/db/chroma/` (Vector)

#### Inspiration 티어 시스템
```
ephemeral → short_term → long_term → core
   30%/일     10%/일       2%/일      영구
```

**승격 조건**:
- `ephemeral → short_term`: strength ≥ 0.3
- `short_term → long_term`: reinforcement ≥ 3회
- `long_term → core`: reinforcement ≥ 10회

**강화 (Reinforcement)**:
- 유사 콘텐츠 봄 → +0.1 strength
- 같은 주제 검색 → +0.05 strength
- 글로 사용 → +0.3 strength + 3 count

### 품질 경쟁 시스템 (v2)
**기존**: 티어별 hard limit (100/50/20)
**변경**: soft ceiling + 하위 % 가속 감쇠

```python
# tier_manager.py
MemoryCapacityConfig:
  soft_ceiling: 500           # 전체 영감 soft ceiling
  bottom_percentile: 0.10     # 하위 10% 가속 감쇠
  accelerated_decay_multiplier: 2.0  # 감쇠 2배
  min_strength_to_survive: 0.05      # 최소 생존 강도
```

**효과**:
- 활동 많으면 → 강한 기억 많음 → 용량 자연 증가
- 활동 적으면 → 약한 기억만 → 자연히 적게 유지
- 특정 도메인 집중 → 해당 기억이 상대적으로 강함 → 더 많이 생존
- 티어별 고정 한계 없음 → 사람처럼 경험에 따라 용량 성장

### Core Memory
`long_term` → `core` 승격 시 생성
```
obsession: 집착 주제 (reinforcement ≥ 15)
opinion: 확고한 의견
theme: 반복 테마 (used ≥ 3)
```

### Vector Search
**파일**: `agent/memory/vector_store.py` → ChromaDB + Gemini Embedding

- Episodes: 경험 임베딩
- Inspirations: 영감 임베딩 (유사 콘텐츠 강화용)
- 유사도 threshold: 0.3 (L2 거리)

### Consolidation (정리)
**파일**: `agent/memory/consolidator.py`

1시간마다 실행:
1. 모든 영감 강도 계산 (감쇠 적용)
2. 하위 10% 가속 감쇠 (2배)
3. min_strength 이하 삭제
4. 승격/강등 처리

## Dev Notes

- 페르소나 구조 확정: `personas/{name}/` 폴더 기반
- **세션 기반 활동 (v3)**: step 반복 → session 반복 (더 사람다운 bursty 패턴)
- **알림 중복 처리**: `processed_notifications`로 이미 처리한 알림 필터링
- **speech_style 간소화**: 규칙 기반 → 예시 기반 (pattern_tracker.py 삭제)
- Threads 연동 deprecated (API 실패)
- 관계도 시스템: 정규식 매칭 + 조건부 평가 지원
- Memory decay: 5 session마다 curiosity 감쇠 (0.7 비율)
- Follow Engine: 지연 실행 큐로 봇 감지 회피
- Activity Scheduler: 시간대별 활동 강도로 세션 간격 동적 조절
- Mode Manager: 226 에러 시 자동 안전 모드 전환
- TopicSelector: 가중치 기반 토픽 선택 (core=1.0, time=1.2, curiosity=2.0, inspiration=2.5, trends=1.5)
- **Knowledge Base**: 트렌드 키워드 조사 후 컨텍스트 저장 (24h 만료)
  - 트렌드 수집 시 자동 학습 (`platforms/twitter/trends.py` → `knowledge_base.learn_topic()`)
  - 포스팅 시 관련 지식 조회 → LLM 프롬프트에 배경지식 추가
  - 관련도 기반 필터링 (`min_relevance=0.2`)
- **Curiosity 확장**: count뿐 아니라 first_seen, last_seen, sources 추적

## Architecture & Future Plans

### 현재 구조 (A: 오픈소스 배포용)

```
config/active_persona.yaml      # 현재 활성 페르소나 지정
personas/*.yaml               # YAML 파일 로딩
agent_memory.json            # JSON 파일 저장
.env                        # 환경변수 인증
python main.py              # 단일 프로세스 실행
```

**특징**: 1인 1프로세스, 로컬 실행, 페르소나 폴더 복사로 교체

### 데이터 접근 지점 (DB 전환 시 수정 대상)

| 데이터 | 현재 | 로딩 위치 |
|--------|------|----------|
| 페르소나 설정 | YAML | `agent/persona/persona_loader.py` |
| 행동 설정 | YAML | `agent/persona/persona_loader.py` |
| 세션 메모리 | JSON | `agent/memory/session.py` |
| 장기 메모리 | SQLite + ChromaDB | `agent/memory/factory.py` |
| 관계 설정 | YAML | `agent/persona/relationship_manager.py` |
| Twitter 인증 | .env + 쿠키 | `platforms/twitter/social.py` |

### 향후 확장 (B: SaaS 서비스용)

```
현재 (A)                          SaaS (B)
────────────────────────────────────────────────────
personas/*.yaml            →     DB (personas 테이블)
.env (Twitter 인증)        →     DB (encrypted credentials) + OAuth
agent_memory.json          →     DB (memories 테이블, user_id FK)
data/posted_content.txt    →     DB (sessions 테이블)
python main.py (1개)       →     Worker Pool (N개 프로세스)
없음                       →     API 서버 (CRUD, 대시보드)
없음                       →     Job Queue (Redis/Celery)
```

### 마이그레이션 전략

**1단계 (현재 완료)**: 하드코딩 제거
- `behavior.yaml`로 시간대 키워드/기분 이동
- 페르소나 폴더 복사 = 완전 독립

**2단계 (선택)**: 스키마 명시화
- Pydantic 모델로 설정 검증
- `persona_loader.py`에서 타입 체크

**3단계 (SaaS 전환 시)**: Provider 패턴
```python
class PersonaProvider(ABC):
    def get_config(self, persona_id) -> PersonaConfig
    def get_behavior(self, persona_id) -> BehaviorConfig

class FileProvider(PersonaProvider):    # 현재
    def get_config(self, persona_id):
        return yaml.load(f"personas/{persona_id}/...")

class DBProvider(PersonaProvider):      # 나중에
    def get_config(self, persona_id):
        return db.query(Persona).get(persona_id)
```

**핵심**: `agent/persona/persona_loader.py` 내부만 수정하면 DB 전환 완료

## Platform Abstraction

Adapter 패턴으로 플랫폼 추상화:

```
agent/platforms/
├── interface.py              # SocialPlatformAdapter 인터페이스
└── twitter/
    └── adapter.py            # TwitterAdapter (platforms/twitter/social.py 래퍼)

platforms/
└── twitter/                  # Twitter API 구현 (Twikit)
    ├── social.py
    └── trends.py
```

**데이터 흐름**:
```
main.py → TwitterAdapter → platforms/twitter/social.py → Twikit → Twitter API
```

**확장 시 변경 지점**:
- `platforms/{platform}/social.py`: 플랫폼별 API 구현
- `agent/platforms/{platform}/adapter.py`: 플랫폼 어댑터 구현 (SocialPlatformAdapter 상속)
- `main.py`: 어댑터 선택 로직 추가
