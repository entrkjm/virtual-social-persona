# Architecture Overview

## System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main.py (Entry)                              │
│                              │                                       │
│                     Virtuals G.A.M.E Agent                           │
│                              │                                       │
│                    ┌─────────┴─────────┐                             │
│                    │    step() loop    │                             │
│                    │  (30s ~ 5m 간격)   │                             │
│                    └─────────┬─────────┘                             │
│                              │                                       │
│              ┌───────────────┼───────────────┐                       │
│              ▼               ▼               ▼                       │
│      scout_timeline    check_mentions   post_tweet                   │
│      (타임라인 정찰)     (멘션 확인)      (독립 글)                    │
│                        │               │                             │
│              ┌─────────┴────────────┐  │                             │
│              ▼                      ▼  ▼                             │
│        [Social Mode]          [Casual Mode]                          │
│        [Series Mode]          [Learning Mode]                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Pipeline: Scout → Perceive → Behavior → Judge → Action

```
┌──────────────────────────────────────────────────────────────────┐
│  SCOUT                                                            │
│  ├─ 3-Layer 키워드 수집                                            │
│  │   ├─ Core: 페르소나 핵심 관심사 (요리, 레시피...)                  │
│  │   ├─ Curiosity: 최근 학습된 관심사 (단기기억)                     │
│  │   └─ Trends: 실시간 트위터 트렌드                                 │
│  └─ Twitter 검색 → 8개 트윗 수집 → 1개 랜덤 선택                     │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  PERCEIVE (LLM)                                                   │
│  ├─ 트윗 분석: topics, sentiment, intent, relevance               │
│  ├─ my_angle: 요리사 관점에서의 해석                                │
│  └─ emotional_impact 계산                                         │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  MEMORY                                                           │
│  ├─ Episode 기록 (SQLite)                                         │
│  ├─ Inspiration 생성 (impact ≥ 0.6 & my_angle 있을 때)             │
│  ├─ 기존 Inspiration 강화 (유사 콘텐츠 감지 via Chroma)              │
│  └─ 트렌드 키워드 → 단기기억 저장                                    │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  BEHAVIOR (확률 기반)                                              │
│  ├─ should_interact(): 상호작용 여부 결정                          │
│  │   ├─ 내향성 (85%) → 확률 감소                                   │
│  │   ├─ 시간대별 기분 변동                                         │
│  │   ├─ 피로도 (10회/일 이상 → 소극적)                              │
│  │   ├─ 쿨다운 (같은 유저 2시간)                                    │
│  │   └─ 현타 시스템 (같은 글 댓글 2회 이상 시)                       │
│  └─ decide_actions(): 독립 확률로 각 행동 결정                      │
│       ├─ like: 60%                                                │
│       ├─ repost: 15%                                              │
│       └─ comment: 12%                                             │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  JUDGE (LLM) - comment=True일 때만                                │
│  ├─ 페르소나 + 관계 + 기분 + 최근 글 컨텍스트                        │
│  └─ 댓글 내용 생성                                                 │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  ACTION (Twitter API via Twikit)                                  │
│  ├─ favorite_tweet()                                              │
│  ├─ repost_tweet()                                                │
│  └─ post_tweet(reply_to=...)                                      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  FOLLOW (상호작용 후)                                              │
│  ├─ 자격 검증 (프로필, 봇 체크)                                     │
│  ├─ 점수 계산 (맞팔, 키워드, 상호작용 이력)                          │
│  ├─ 확률 결정 (base 15% + 보너스)                                  │
│  └─ 지연 실행 (30초~5분 후 큐에서 처리)                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Content Generation Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│  ContentGenerator (Unified)                                       │
│  ├─ generate_reply() / generate_post()                            │
│  │                                                                │
│  ├─ _validate_and_regenerate() (최대 3회)                          │
│  │   ├─ 금지 문자 체크 (한자, 일본어)                                │
│  │   └─ 위반 시 재생성                                             │
│  │                                                                │
│  └─ _review_content() (LLM 리뷰)                                   │
│      ├─ PatternTracker.check_violations()                         │
│      │   ├─ signature 쿨다운 체크 (5 posts)                        │
│      │   ├─ frequent 연속 사용 체크 (max 2)                        │
│      │   ├─ filler 과다 사용 체크 (max 1/post)                     │
│      │   └─ contextual 맥락 체크                                   │
│      ├─ LLM에게 교정 요청 (위반 사항 명시)                           │
│      └─ PatternTracker.record_usage()                             │
└──────────────────────────────────────────────────────────────────┘
```

### Pattern Registry (persona.yaml)

```yaml
pattern_registry:
  signature:  # 시그니처 표현 (특별할 때만)
    patterns: ["나야~ 들기름"]
    cooldown_posts: 5
  frequent:   # 자주 쓰는 어미 (연속 금지)
    patterns: ["~거든요", "~인 거죠"]
    max_consecutive: 2
  filler:     # 채움말 (글당 1회)
    patterns: ["음...", "어..."]
    max_per_post: 1
  contextual: # 맥락별 조절
    serious_topic: { avoid: ["ㅎㅎ"], prefer: ["~입니다"] }
```

---

## Follow Engine

```
상호작용 발생
    ↓
┌─────────────────────────────────┐
│ 1. Eligibility Check            │
│    - 이미 팔로우 중? → SKIP      │
│    - 프로필 없음? → SKIP         │
│    - 팔로워 비율 < 0.1? → SKIP   │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 2. Score Calculation (0-100)    │
│    - 맞팔 여부: +30              │
│    - 바이오 키워드: +20          │
│    - 상호작용 이력: +20          │
│    - 계정 품질: +10             │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 3. Probability Decision         │
│    - base: 15%                  │
│    - score 40+: +15%            │
│    - score 70+: +25%            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 4. Delayed Execution            │
│    - 30초~5분 지연               │
│    - 일일 한도: 20회             │
└─────────────────────────────────┘
```

---

## Memory System

### Dual Storage

| Storage | 용도 |
|---------|------|
| **SQLite** (`data/memory.db`) | 구조화 데이터 (CRUD, 쿼리, 통계) |
| **Chroma** (`data/chroma/`) | 벡터 임베딩 (시맨틱 검색) |

### Memory Tiers

```
경험 (Episode)
    ↓
Ephemeral (순간) → 빠른 감쇠, 48시간 내 강화 없으면 삭제
    ↓ [strength > 0.3]
Short-term (단기) → 1-2회 강화된 영감
    ↓ [reinforcement ≥ 3]
Long-term (장기) → 글 발현 후보
    ↓ [reinforcement ≥ 5, 페르소나 영향]
Core (핵심) → 영구 보존, 페르소나 통합
```

### Key Concepts

- **Episode**: 모든 경험 기록 (saw_tweet, replied, liked, posted)
- **Inspiration**: 글감, 영감 (trigger + my_angle + potential_post)
- **Reinforcement**: 유사 콘텐츠 재노출 시 영감 강화
- **Consolidation**: 주기적 정리 (감쇠, 승격, 강등)

---

## Component Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│  agent/                                                            │
│  ├── bot.py                # SocialAgent (메인 워크플로우)           │
│  ├── core/                 # 플랫폼 독립 로직                        │
│  │   ├── behavior_engine.py                                        │
│  │   ├── content_generator.py                                      │
│  │   └── interaction_intelligence.py                               │
│  ├── memory/               # 동적 메모리 시스템 (DB, Session)        │
│  ├── knowledge/            # 지식 시스템                             │
│  ├── persona/              # 페르소나 로딩 및 관리                   │
│  │                                                                 │
│  ├── platforms/            # [NEW] 플랫폼별 구현                     │
│  │   └── twitter/                                                  │
│  │       ├── modes/        # Casual/Social/Series 모드 구현          │
│  │       └── learning/     # 트렌드 학습 구현                        │
│  │                                                                 │
│  actions/                  # (Legacy - to be removed)              │
│  core/                                                             │
│   └── llm.py               # 멀티 LLM 클라이언트                      │
│                            # (Gemini, OpenAI, Anthropic)            │
│                                                                    │
│  config/                                                           │
│     ├── settings.py          # 환경변수 + 설정                          │
│     └── personas/            # 페르소나 폴더                            │
│         └── chef_choi/       # 페르소나별 독립 폴더                     │
│             ├── identity.yaml       # 핵심 정체성                       │
│             ├── speech_style.yaml   # 말투 패턴                        │
│             ├── mood.yaml           # 기분 & 스케줄                     │
│             ├── core_relationships.yaml # 핵심 관계                    │
│             ├── prompt.txt         # 시스템 프롬프트                    │
│             └── platforms/          # 플랫폼 설정                       │
│                 └── twitter/                                          │
│                     ├── config.yaml # 제약 사항                        │
│                     └── modes/      # 모드별 config.yaml + style.yaml  │
└────────────────────────────────────────────────────────────────────┘
```

---

## LLM Integration

```python
# 설정 (.env)
LLM_PROVIDER=gemini  # gemini | openai | anthropic

# 사용
from core.llm import llm_client
response = llm_client.generate(prompt, system_prompt)
```

### Supported Providers

| Provider | Model (Default) | 용도 |
|----------|-----------------|------|
| Gemini | gemini-2.5-flash | 기본, 무료 티어 |
| OpenAI | gpt-4o-mini | 대체 옵션 |
| Anthropic | claude-sonnet-4 | 대체 옵션 |

---

## Configuration

### Environment Variables (.env)

```bash
# Required
GAME_API_KEY=...          # Virtuals Protocol
GEMINI_API_KEY=...        # Gemini API

# Twitter 인증은 쿠키 파일 사용
# data/cookies/{persona_name}_cookies.json

# Optional
LLM_PROVIDER=gemini       # gemini | openai | anthropic
DATA_DIR=data             # 데이터 저장 경로
```

### Behavior Tuning (config/behavior.yaml)

```yaml
step_interval:
  min: 30
  max: 300

action_probability:
  lurk: 0.40
  like_only: 0.30
  comment: 0.25

posting_trigger:
  flash: 0.70
  mood_burst: 0.30
```

---

## Data Flow

```
Twitter Search ──→ Episode (SQLite) ──→ Vector Embedding (Chroma)
                         │
                         ▼
              [impact ≥ 0.6 & my_angle]
                         │
                         ▼
              Inspiration (ephemeral)
                         │
              ┌──────────┴──────────┐
              │                     │
         [강화 없음]            [유사 콘텐츠 재노출]
              │                     │
              ▼                     ▼
           삭제 (48h)         strength++, tier 승격
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                    [long_term]           [core]
                         │                     │
                         ▼                     ▼
                   글 발현 후보          페르소나 통합
```

---

## API Actions

| Action | Description | Trigger |
|--------|-------------|---------|
| `scout_timeline` | 타임라인 정찰 + 반응 | SDK step() |
| `check_mentions` | 멘션/답글 확인 + 반응 | SDK step() |
| `post_tweet` | 독립 글 게시 | SDK 또는 Posting Trigger |

---

## Related Docs

- [MEMORY_SYSTEM_DESIGN.md](./MEMORY_SYSTEM_DESIGN.md) - 메모리 시스템 상세 설계
- [BEHAVIOR_CONFIG_GUIDE.md](./BEHAVIOR_CONFIG_GUIDE.md) - 행동 설정 가이드
- [CLAUDE.md](../CLAUDE.md) - 개발 지침
