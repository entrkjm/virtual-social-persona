# Virtual Agent

Virtuals Protocol G.A.M.E SDK 기반 자율형 트위터 AI 에이전트.

## Quick Start

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 편집: API 키 입력

# 실행
python main.py
```

## Core Flow

```
Scout → Perceive → Behavior → Judge → Action → Follow
```

| Stage | 역할 |
|-------|------|
| Scout | 3-Layer 키워드로 트윗 검색 (Core + Curiosity + Trends) |
| Perceive | LLM으로 트윗 분석 (topics, sentiment, my_angle) |
| Behavior | 확률 기반 행동 결정 (like 60%, repost 15%, comment 12%) |
| Judge | LLM으로 댓글 내용 생성 (comment=True일 때) |
| Action | Twitter API 호출 |
| Follow | 상호작용 후 점수 기반 팔로우 판단 + 지연 실행 |

## Structure

```
agent/                    # Brain
  bot.py                  # 메인 워크플로우
  core/                   # 플랫폼 독립 로직 (8개 모듈)
  memory/                 # 메모리 시스템 (DB, Vector, Session)
  knowledge/              # 지식 시스템
  persona/                # 페르소나 로딩 및 관리
  platforms/              # 플랫폼별 구현
    twitter/              # Twitter 플랫폼
      modes/              # 실행 모드 (Casual/Social/Series)
      learning/           # 트렌드 학습

core/                     # Heart
  llm.py                  # 멀티 LLM (Gemini, OpenAI, Anthropic)

config/                   # Settings
  active_persona.yaml     # 활성 페르소나 지정
  personas/               # 페르소나 폴더
    chef_choi/            # 셰프 최강록
      identity.yaml       # 핵심 정체성
      speech_style.yaml   # 말투 패턴
      mood.yaml           # 기분 및 스케줄
      core_relationships.yaml # 핵심 관계
      prompt.txt          # 시스템 프롬프트
      platforms/          # 플랫폼별 설정
        twitter/
          config.yaml     # 플랫폼 제약
          step_schedule.yaml # 행동 비중
          modes/          # 모드별 설정 (config.yaml + style.yaml)

data/                     # Runtime Data
  memory.db               # SQLite (에피소드, 영감, 메모리)
  chroma/                 # 벡터 임베딩 (시맨틱 검색)
```

## Key Features

- **3-Layer Intelligence**: Core 정체성 + 학습된 관심사 + 실시간 트렌드
- **Dynamic Memory**: 경험 → 영감 → 장기기억 (감쇠/강화/승격)
- **Human-like Behavior**: 내향성, 기분 변동, 피로도, 현타 시스템
- **Independent Actions**: 좋아요/리포스트/댓글 각각 독립 확률
- **Chat/Post Style**: 답글과 독립 포스팅 스타일 분리
- **Pattern Management**: 3-Layer 말투 패턴 관리 (signature/frequent/filler/contextual)
- **Smart Follow**: 점수 기반 팔로우 판단 + 지연 실행 (봇 감지 회피)
- **SDK Optional**: Virtuals SDK 사용 여부 선택 가능 (USE_VIRTUAL_SDK)

## Persona

새 페르소나 추가:
```bash
cp -r config/personas/_template config/personas/my_persona
# 파일 수정 후
# config/active_persona.yaml → active: "my_persona"
```

사용 가능 페르소나 확인:
```python
from agent.persona_loader import PersonaLoader
print(PersonaLoader.list_personas())
```

## Configuration

```bash
# .env
GAME_API_KEY=...              # Virtuals Protocol (SDK 모드 시 필수)
GEMINI_API_KEY=...            # Gemini API
LLM_PROVIDER=gemini           # gemini | openai | anthropic
USE_VIRTUAL_SDK=false         # true: SDK 모드, false: Standalone 모드

# Twitter 인증 (둘 중 하나)
TWITTER_USERNAME=...
TWITTER_PASSWORD=...
# 또는
TWITTER_AUTH_TOKEN=...
TWITTER_CT0=...
```

## Data

| 경로 | 용도 |
|------|------|
| `data/memory.db` | SQLite - 에피소드, 영감, 포스트 기록 |
| `data/chroma/` | Chroma - 벡터 임베딩 (시맨틱 검색) |

## Docs

- [Architecture](./docs/ARCHITECTURE.md) - 전체 아키텍처
- [Memory System](./docs/MEMORY_SYSTEM_DESIGN.md) - 메모리 시스템 설계
- [Behavior Config](./docs/BEHAVIOR_CONFIG_GUIDE.md) - 행동 설정 가이드
