# Virtual Agent 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**자율형 소셜 미디어 AI 에이전트** - LLM 기반 인간 같은 트위터 봇

[English README](./README.md)

---

## ✨ 주요 기능

- 🧠 **3계층 지능**: 핵심 정체성 + 학습된 관심사 + 실시간 트렌드
- 💾 **동적 메모리**: 경험 → 영감 → 장기 기억 (감쇠/강화 시스템)
- 🎭 **인간적 행동**: 기분 변동, 피로도, 성격 특성
- 🔄 **독립 행동**: 좋아요/리포스트/댓글 확률 개별 계산
- 🔌 **플랫폼 독립**: 어댑터 패턴으로 플랫폼 교체 용이
- 👥 **멀티 페르소나**: 환경변수로 여러 페르소나 동시 실행

---

## 🚀 빠른 시작

```bash
# 클론
git clone https://github.com/YOUR_USERNAME/virtual.git
cd virtual

# 의존성 설치
pip install -r requirements.txt

# 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 실행
python main.py
```

---

## 🔧 설정

### 필수 환경변수

```env
# LLM (하나 선택)
GEMINI_API_KEY=your_gemini_key
# 또는 USE_VERTEX_AI=true + GCP 인증

# Twitter (쿠키 인증 - 권장)
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CT0=your_ct0_token
```

### Twitter 쿠키 얻기

1. 브라우저에서 twitter.com 로그인
2. 개발자 도구 → Application → Cookies → twitter.com
3. `auth_token`과 `ct0` 값 복사
4. 또는: `python scripts/manage_cookies.py import cookies.json`

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│                      (진입점)                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      SocialAgent                        │
│                      (bot.py)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   Scout     │→ │   Perceive  │→ │   Decide/Act    │ │
│  │  (검색)     │  │ (LLM 분석)  │  │  (행동 결정)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Memory   │   │  Persona  │   │  Platform │
    │  System   │   │  Loader   │   │  Adapter  │
    │ (SQLite+  │   │ (YAML)    │   │ (Twitter) │
    │  Chroma)  │   │           │   │           │
    └───────────┘   └───────────┘   └───────────┘
```

---

## 📁 프로젝트 구조

```
virtual/
├── agent/                    # 핵심 에이전트 로직
│   ├── bot.py               # 메인 워크플로우
│   ├── core/                # 플랫폼 독립 모듈
│   ├── memory/              # 메모리 시스템 (DB, Vector)
│   ├── persona/             # 페르소나 로딩
│   └── platforms/           # 플랫폼 어댑터
│       └── twitter/         # Twitter 구현
│           ├── adapter.py   # 플랫폼 어댑터
│           ├── api/         # API 래퍼 (twikit)
│           └── modes/       # 실행 모드
│               ├── casual/  # 독립 포스팅
│               ├── social/  # 상호작용 & 답글
│               └── series/  # 테마 콘텐츠 시리즈
│
├── personas/                # 페르소나 설정
│   └── chef_choi/          # 예시: 셰프 페르소나
│       ├── identity.yaml   # 핵심 정체성
│       ├── speech_style.yaml
│       └── platforms/twitter/
│
├── core/                    # 공통 유틸리티
│   └── llm.py              # 멀티 LLM 클라이언트
│
├── scripts/                 # 유틸리티 스크립트
│   └── manage_cookies.py   # 쿠키 관리 CLI
│
└── docs/                    # 문서
```

---

## 🎭 멀티 페르소나 배포

한 PC에서 여러 페르소나 실행:

```bash
# 터미널 1 - 페르소나 A
PERSONA_NAME=chef_choi python main.py

# 터미널 2 - 페르소나 B (다른 트위터 계정)
PERSONA_NAME=client_a \
TWITTER_AUTH_TOKEN="client_a_token" \
TWITTER_CT0="client_a_ct0" \
python main.py
```

`screen` 백그라운드 실행:
```bash
screen -S chef
PERSONA_NAME=chef_choi python main.py
# Ctrl+A, D로 detach

screen -ls  # 세션 목록
screen -r chef  # 다시 연결
```

---

## 📊 실행 모드

| 모드 | 설명 |
|------|------|
| `normal` | 일반 동작 (수면 스케줄 적용) |
| `test` | 빠른 반복, 제한 없음 |
| `aggressive` | 최대 활동, 휴식 없음 |

```bash
AGENT_MODE=aggressive python main.py
```

---

## 🛡️ 플랫폼 지속가능성

이 프로젝트는 `twikit` (비공식 Twitter 라이브러리)를 사용합니다. Twitter 내부 API 변경 시 동작이 중단될 수 있습니다.

**대비책 - 어댑터 패턴**:
- 모든 Twitter 코드는 `agent/platforms/twitter/`에 격리
- `bot.py`는 추상 `SocialPlatformAdapter` 인터페이스만 사용
- Playwright나 공식 API로 교체 시 어댑터만 수정하면 됨

---

## 📚 문서

- [배포 가이드](./docs/DEPLOYMENT_STRATEGY.md)
- [메모리 시스템 설계](./docs/MEMORY_SYSTEM_DESIGN.md)
- [변경 로그](./docs/CHANGELOG_20260120.md)

---

## 📄 라이선스

MIT License - [LICENSE](./LICENSE) 참조

---

## ⚠️ 면책 조항

이 프로젝트는 교육 목적입니다. 책임감 있게 사용하고 Twitter 이용약관을 준수하세요. 오용이나 계정 정지에 대해 저자는 책임지지 않습니다.
