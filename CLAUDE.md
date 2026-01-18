# Virtual Agent (Dev)

Virtuals Protocol G.A.M.E SDK 기반 자율형 트위터 AI 에이전트. 사람다운 행동 패턴을 구현한 자율 소셜 에이전트.

## Core Flow

```
main.py (Entry)
    ↓
run_with_sdk() 또는 run_standalone() (USE_VIRTUAL_SDK 설정)
    ↓
ActivityScheduler (수면/활동 패턴 확인)
    ↓
step() 루프 (ModeManager에 따라 가변 간격)
    ↓
scout_timeline (80%) | check_mentions (15%) | post_tweet (5%)
    ↓
Scout → Perceive → Behavior → Judge → Action → Follow
```

### 6-Stage Pipeline

| Stage | 담당 | 역할 |
|-------|------|------|
| Scout | `bot.py` | 3-Layer 키워드로 트윗 검색 |
| Perceive | `interaction_intelligence.py` | LLM으로 트윗 의미/감정/의도 분석 |
| Behavior | `behavior_engine.py` + `human_like_controller.py` | 확률 기반 사람다운 판단 (기분/현타/피로) + 워밍업/지연/버스트 방지 |
| Judge | `content_generator.py` | 콘텐츠 생성 + 패턴 검증 + 리뷰 |
| Action | `actions/social.py` | Twitter API 호출 (액션 지연 적용) |
| Follow | `follow_engine.py` | 점수 기반 팔로우 판단 + 지연 실행 |

## 3-Layer Intelligence

| Layer | 소스 | 용도 |
|-------|------|------|
| Core | `persona.yaml` | 페르소나 본질 (요리사 정체성) |
| Curiosity | `memory.py` | 최근 관심사 (자동 학습/감쇠) |
| Trends | `trends.py` | 실시간 트위터 트렌드 |

## Key Components

| 파일 | 역할 |
|------|------|
| `agent/bot.py` | SocialAgent 클래스, 전체 워크플로우 |
| `agent/behavior_engine.py` | BehaviorEngine - 확률 기반 행동 판단 (기분/현타/피로) |
| | HumanLikeController - 워밍업/지연/버스트 방지/에러 핸들링 |
| `agent/content_generator.py` | chat/post 스타일 분리 콘텐츠 생성 + 검증 + LLM 리뷰 |
| `agent/pattern_tracker.py` | 3-Layer 말투 패턴 추적 (signature/frequent/filler/contextual) |
| `agent/activity_scheduler.py` | **[NEW]** 사람다운 휴식 패턴 (수면/시간대별 활동/랜덤 휴식/오프데이) |
| `agent/mode_manager.py` | **[NEW]** Test 모드 시스템 (normal/test/aggressive) |
| `agent/follow_engine.py` | 점수 기반 팔로우 판단 + 지연 큐 |
| `agent/memory.py` | AgentMemory - interactions, facts, curiosity, relationships |
| `agent/interaction_intelligence.py` | LLM 기반 트윗 분석/판단 |
| `agent/relationship_manager.py` | 유저 관계 추적 (사전정의 + 동적) |
| `agent/persona_loader.py` | YAML 기반 페르소나 로딩 |
| `actions/social.py` | Twikit 기반 Twitter API + follow 기능 |
| `actions/trends.py` | 트렌드 수집 |
| `core/llm.py` | 멀티 LLM 클라이언트 (Gemini, OpenAI, Anthropic) |

## Behavior Engine

`agent/behavior_engine.py` + `config/personas/chef_choi/behavior.yaml`

### BehaviorEngine (확률 기반 판단)
- **확률 기반 판단**: 같은 상황에서도 다르게 반응
- **기분 변동**: 시간대/최근 상호작용/랜덤 요소
- **현타 시스템**: 같은 글에 댓글 많이 달면 자제
- **피로도**: 하루 10회 이상 상호작용 시 소극적
- **집착 주제**: 관심 주제면 쿨다운 무시
- **독립 확률**: like/repost/comment가 독립적으로 판단

### HumanLikeController (봇 탐지 회피)
- **워밍업**: 처음 N스텝 동안 읽기만 (액션 없음)
- **액션 지연**: like 후 2-5초, comment 후 5-15초, post 후 30-120초
- **버스트 방지**: 연속 3회 액션 후 쿨다운
- **에러 핸들링**: 226 에러 시 30분 정지 + 확률 감소, 404 에러 시 5분 정지

### 튜닝 가능 설정 (behavior.yaml)
```yaml
personality_traits:
  introversion: 0.85      # 내향성
  obsessiveness: 0.80     # 집착도

interaction_patterns:
  same_user:
    max_interactions_per_day: 3
    cooldown_minutes: 120
  same_post:
    max_comments_per_post: 2
    regret_probability: 0.30
  independent_actions:    # normal 모드에서 사용 (test/aggressive는 오버라이드)
    like_probability: 0.40
    repost_probability: 0.10
    comment_probability: 0.08

# Human-like 행동
human_like:
  warmup:
    enabled: true
    steps: 5              # 처음 5스텝 읽기만
  action_delays:
    after_like: [2, 5]
    after_comment: [5, 15]
    after_post: [30, 120]
  burst_prevention:
    max_consecutive_actions: 3
    cooldown_after_burst: 60
  error_handling:
    on_226:
      pause_minutes: 30
      reduce_probability: 0.5
    on_404:
      pause_minutes: 5

# 활동 스케줄 (사람다운 휴식)
activity_schedule:
  sleep_pattern:
    base_sleep_start: 1   # 새벽 1시
    base_wake_time: 7     # 오전 7시
    variance:
      sleep_start: 2      # ±1시간
      wake_time: 1.5      # ±45분
    exceptions:
      late_night_probability: 0.15
      early_wake_probability: 0.10
      midnight_check_probability: 0.08  # 새벽 폰 체크
    weekend_modifier:
      sleep_start: 1
      wake_time: 2
  hourly_activity:        # 시간대별 활동 강도
    "07-09": 0.3
    "09-12": 0.7
    "14-18": 0.8
    "18-22": 1.0
  random_breaks:
    enabled: true
    probability: 0.15
    duration_min: 30
    duration_max: 180
  random_off_day:
    enabled: true
    probability: 0.10     # 하루 쉴 확률

# 팔로우 행동
follow_behavior:
  enabled: true
  daily_limit: 20
  base_probability: 0.15
  score_threshold: 40
  delay:
    min: 30
    max: 300

# 콘텐츠 리뷰
content_review:
  enabled: true
  patterns_to_moderate: ["~거든요", "음..."]
  max_pattern_occurrences: 1
```

## Persona System

```
config/active_persona.yaml              # 현재 활성 페르소나 지정
config/personas/
  chef_choi/                            # 페르소나별 독립 폴더
    persona.yaml                        # 설정 + pattern_registry + speech_style
    behavior.yaml                       # 행동 확률 + human_like + activity_schedule
    relationships.yaml                  # 관계도
    prompt.txt                          # 시스템 프롬프트
    rules.txt                           # 소통 규칙
  _template/                            # 새 페르소나 템플릿
```

### Pattern Registry (persona.yaml)
```yaml
pattern_registry:
  signature:    # 시그니처 표현 (5포스트당 1회)
    patterns: ["나야~ 들기름"]
    cooldown_posts: 5
  frequent:     # 자주 쓰는 어미 (연속 2회 제한)
    patterns: ["~거든요", "~인 거죠"]
    max_consecutive: 2
  filler:       # 채움말 (글당 1회)
    patterns: ["음...", "어..."]
    max_per_post: 1
  contextual:   # 맥락별 조절
    serious_topic: { avoid: ["ㅎㅎ"], prefer: ["~입니다"] }

speech_style:   # 콘텐츠 생성 스타일 분리
  chat:         # 답글/대화 모드
    length: { min: 20, max: 150 }
    tone: "친근하고 도움주는"
    starters: ["음...", "아..."]
    endings: ["~요", "~거든요"]
  post:         # 독립 포스팅 모드
    length: { min: 30, max: 280 }
    tone: "짧고 임팩트 있게"
    starters: ["갑자기 생각났는데", "요즘 느끼는 건데"]
    endings: ["~임", "..."]
```

## External Dependencies

| 라이브러리 | 용도 | 주의사항 |
|-----------|------|---------|
| `virtuals-game-sdk` | Agent 프레임워크 | 429 rate limit 빈번, retry 로직 필수 |
| `twikit` | Twitter 비공식 SDK | 쿠키 인증 필요 (auth_token, ct0) |
| `google-generativeai` | Gemini LLM | API 키 필수 |

## DO NOT TOUCH

| 파일/폴더 | 이유 |
|----------|------|
| `.env` | API 키, Twitter 인증 정보 |
| `chrome_data/` | Twitter 세션 데이터 |
| `agent_memory.json` | 런타임 메모리 (interactions, relationships) |
| `posted_content.txt` | 게시 로그 |

## Mode System

`agent/mode_manager.py` + 환경변수 `AGENT_MODE`

| Mode | 간격 | 확률 | 워밍업 | 수면 | 휴식 | 용도 |
|------|------|------|--------|------|------|------|
| **normal** | 60-180s | **페르소나 값** | 5스텝 | O | O | 프로덕션 |
| **test** | 15-45s | 50/15/10% | 2스텝 | X | X | 테스트 |
| **aggressive** | 8-20s | 70/25/15% | 0스텝 | X | X | 개발 (주의!) |

### 동작
- **normal**: 페르소나 `behavior.yaml`의 `independent_actions` 값 그대로 사용 (프로덕션용)
- **test/aggressive**: 모드별 고정 확률로 오버라이드 (개발용)
- 226 에러 발생 시 aggressive → normal 자동 전환
- 연속 3회 에러 시 normal로 전환 + 5분 정지

### 페르소나 이식성
```
normal 모드 = 페르소나 100% 존중
├── 확률: behavior.yaml의 independent_actions
├── 성격: personality_traits
└── 스타일: persona.yaml의 speech_style

→ 페르소나 폴더 복사 + active_persona.yaml 변경 = 완전 교체
```

### 사용 예시
```bash
# normal 모드 (기본)
AGENT_MODE=normal python main.py

# test 모드 (빠른 테스트)
AGENT_MODE=test python main.py

# aggressive 모드 (실험용, 봇 감지 위험)
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

`agent/content_generator.py` - chat/post 스타일 분리 + 검증

### 2가지 생성 모드
| Mode | 용도 | 길이 | 톤 | 예시 시작어 | 예시 끝말 |
|------|------|------|-----|------------|---------|
| **chat** | 답글/대화 | 15-100자 | 친근하고 도움주는 | 음..., 아... | ~요, ~거든요 |
| **post** | 독립 포스팅 | 20-120자 | 짧고 임팩트 | 갑자기 생각났는데 | ~임, ... |

### 검증 레이어
1. **금지 문자 검증**: 한자/일본어 포함 시 재생성 (최대 3회)
2. **Twitter 글자수 검증**: 한글 가중치 적용 (한글 1자 = 2 가중치, 280 제한)
3. **LLM 리뷰 레이어**: Pattern Tracker 연동
   - 과도한 말투 패턴 교정 (`~거든요` 연속 사용 등)
   - 패턴 위반 사항 자동 교정
   - 자연스러운 일반인 글 스타일로 다듬기

### 사용 예시 (코드)
```python
from agent.content_generator import create_content_generator

generator = create_content_generator(persona_config)

# 답글 생성
reply = generator.generate_reply(
    target_tweet={"user": "some_user", "text": "파스타 만들기 어려워요"},
    perception={"sentiment": "neutral", "topics": ["요리"]},
    context={"mood": "평온함", "interests": ["파스타"]}
)

# 독립 포스팅 생성
post = generator.generate_post(
    topic="요리 디테일",
    context={"mood": "평온함", "interests": ["파스타"]}
)
```

## Activity Scheduler

`agent/activity_scheduler.py` - 사람다운 휴식 패턴

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

## Dev Notes

- 페르소나 구조 확정: `config/personas/{name}/` 폴더 기반
- Threads 연동 deprecated (API 실패)
- 관계도 시스템: 정규식 매칭 + 조건부 평가 지원
- Memory decay: 10 step마다 curiosity 감쇠 (0.7 비율)
- Pattern Tracker: SQLite로 패턴 사용 기록 (`data/memory.db`)
- Follow Engine: 지연 실행 큐로 봇 감지 회피
- Activity Scheduler: 시간대별 활동 강도로 step 간격 동적 조절
- Mode Manager: 226 에러 시 자동 안전 모드 전환
