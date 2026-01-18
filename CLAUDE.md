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

## 4-Layer Intelligence

| Layer | 소스 | 용도 |
|-------|------|------|
| Core | `persona.yaml` | 페르소나 본질 (요리사 정체성) |
| Curiosity | `json_memory.py` | 최근 관심사 (자동 학습/감쇠, 소스 추적) |
| Knowledge | `knowledge_base.py` | 트렌드 컨텍스트 (요약/관련도/내 관점) |
| Trends | `trends.py` | 실시간 트위터 트렌드 → Knowledge로 학습

## Key Components

| 파일 | 역할 |
|------|------|
| `agent/bot.py` | SocialAgent 클래스, 전체 워크플로우 |
| `agent/behavior_engine.py` | BehaviorEngine - 확률 기반 행동 판단 (기분/현타/피로) |
| | HumanLikeController - 워밍업/지연/버스트 방지/에러 핸들링 |
| `agent/content_generator.py` | chat/post 스타일 분리 콘텐츠 생성 + 검증 + LLM 리뷰 |
| `agent/pattern_tracker.py` | 3-Layer 말투 패턴 추적 (signature/frequent/filler/contextual) |
| `agent/topic_selector.py` | 가중치 기반 토픽 선택 (core/time/curiosity/trends/inspiration) |
| `agent/knowledge_base.py` | 트렌드/키워드 컨텍스트 학습 (요약, 관련도, 내 관점) |
| `agent/activity_scheduler.py` | 사람다운 휴식 패턴 (수면/시간대별 활동/랜덤 휴식/오프데이) |
| `agent/mode_manager.py` | 모드 시스템 (normal/test/aggressive) + step 확률 관리 |
| `agent/follow_engine.py` | 점수 기반 팔로우 판단 + 지연 큐 |
| `agent/memory.py` | AgentMemory - interactions, facts, curiosity, relationships |
| `agent/interaction_intelligence.py` | LLM 기반 트윗 분석/판단 + ResponseType 결정 |
| `agent/relationship_manager.py` | 유저 관계 추적 (사전정의 + 동적) |
| `agent/persona_loader.py` | YAML 기반 페르소나 로딩 (중앙 로딩 지점) |
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
# 시간대별 검색 키워드 (빈 배열 = core_keywords 사용)
time_keywords:
  morning: ["아침", "조식", "모닝커피"]    # 06-11시
  lunch: ["점심", "메뉴추천", "맛집"]      # 11-14시
  afternoon: []                           # 14-17시 (core_keywords)
  dinner: ["저녁", "회식", "요리법"]       # 17-21시
  late_night: ["야식", "치킨", "맥주"]     # 21-24시
  default: []                             # 그 외

# 시간대별 기분 설명
mood_descriptions:
  morning: "아침 일찍 일어나 재료를 검수하며..."
  lunch: "점심 영업 준비로 극도로 예민하고..."
  afternoon: "영업 후 휴식하며 멍하니..."
  dinner: "저녁 메인 요리를 조리하며..."
  late_night: "늦은 밤, 혼자 술 한 잔 하며..."

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

### 폴더 구조
```
config/active_persona.yaml              # 현재 활성 페르소나 지정
config/personas/
  chef_choi/                            # 페르소나별 독립 폴더
    persona.yaml                        # 정체성 + pattern_registry + speech_style + quip_pool
    behavior.yaml                       # 행동 확률 + time_keywords + mood_descriptions
    relationships.yaml                  # 관계도
    prompt.txt                          # 시스템 프롬프트
    rules.txt                           # 소통 규칙
  _template/                            # 새 페르소나 템플릿 (전체 스키마 포함)
```

### 페르소나 이식성
**페르소나 폴더 복사 = 완전 독립 에이전트**

모든 페르소나 종속 설정이 폴더 내에 포함:
- `persona.yaml`: 정체성 (이름, 키워드, 말투, quip_pool)
- `behavior.yaml`: 행동 패턴 (time_keywords, mood_descriptions, 확률)
- 하드코딩 없음 → 코드 수정 없이 페르소나 교체 가능

```bash
# 새 페르소나 생성
cp -r config/personas/_template config/personas/new_persona
# active_persona.yaml 수정
echo "active_persona: new_persona" > config/active_persona.yaml
# 실행
python main.py
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
| `chromadb` | 벡터 저장소 | **1.4.1+** 필수 (DB 마이그레이션 호환) |

## DO NOT TOUCH

| 파일/폴더 | 이유 |
|----------|------|
| `.env` | API 키, Twitter 인증 정보 |
| `chrome_data/` | Twitter 세션 데이터 |
| `agent_memory.json` | 런타임 메모리 (interactions, relationships) |
| `posted_content.txt` | 게시 로그 |

## Mode System

`agent/mode_manager.py` + 환경변수 `AGENT_MODE`

### Step 확률 (scout / mentions / post)
| Mode | 간격 | Scout | Mentions | Post | 워밍업 | 수면 | 휴식 |
|------|------|-------|----------|------|--------|------|------|
| **normal** | 60-180s | 80% | 15% | 5% | 5스텝 | O | O |
| **test** | 15-45s | 75% | 15% | 10% | 2스텝 | X | X |
| **aggressive** | 8-20s | 70% | 15% | 15% | 0스텝 | X | X |

### Action 확률 (like / repost / comment)
| Mode | Like | Repost | Comment |
|------|------|--------|---------|
| **normal** | 페르소나 값 | 페르소나 값 | 페르소나 값 |
| **test** | 45% | 45% | 12% |
| **aggressive** | 60% | 60% | 18% |

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

`agent/content_generator.py` - ResponseType 기반 분기 + 검증

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

### QUIP Pool (persona.yaml)
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
- TopicSelector: 가중치 기반 토픽 선택 (core=1.0, time=1.2, curiosity=2.0, inspiration=2.5, trends=1.5)
- **Knowledge Base**: 트렌드 키워드 조사 후 컨텍스트 저장 (24h 만료)
  - 트렌드 수집 시 자동 학습 (`trends.py` → `knowledge_base.learn_topic()`)
  - 포스팅 시 관련 지식 조회 → LLM 프롬프트에 배경지식 추가
  - 관련도 기반 필터링 (`min_relevance=0.2`)
- **Curiosity 확장**: count뿐 아니라 first_seen, last_seen, sources 추적

## Architecture & Future Plans

### 현재 구조 (A: 오픈소스 배포용)

```
config/personas/*.yaml    →  YAML 파일 로딩
agent_memory.json         →  JSON 파일 저장
.env                      →  환경변수 인증
python main.py            →  단일 프로세스 실행
```

**특징**: 1인 1프로세스, 로컬 실행, 페르소나 폴더 복사로 교체

### 데이터 접근 지점 (DB 전환 시 수정 대상)

| 데이터 | 현재 | 로딩 위치 |
|--------|------|----------|
| 페르소나 설정 | YAML | `persona_loader.py` |
| 행동 설정 | YAML | `persona_loader.py` |
| 메모리 | JSON | `memory.py` |
| 관계 설정 | YAML | `relationship_manager.py` (persona_loader 경유) |
| Twitter 인증 | .env + 쿠키 | `social.py` |

### 향후 확장 (B: SaaS 서비스용)

```
현재 (A)                          SaaS (B)
─────────────────────────────────────────────────────
config/personas/*.yaml     →     DB (personas 테이블)
.env (Twitter 인증)        →     DB (encrypted credentials) + OAuth
agent_memory.json          →     DB (memories 테이블, user_id FK)
twitter_cookies.json       →     DB (sessions 테이블)
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
        return yaml.load(f"config/personas/{persona_id}/...")

class DBProvider(PersonaProvider):      # 나중에
    def get_config(self, persona_id):
        return db.query(Persona).get(persona_id)
```

**핵심**: `persona_loader.py` 내부만 수정하면 DB 전환 완료
