# 🤖 Virtual Agent - AI 페르소나 프레임워크

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**나만의 AI 캐릭터를 트위터에서 활동시키세요.** 고유한 성격, 기억, 인간적인 행동을 가진 자율형 소셜 미디어 에이전트를 만들 수 있습니다.

[English README](./README.md)

---

## 🎯 이게 뭔가요?

**AI 페르소나**를 만들어서 다음을 할 수 있는 프레임워크입니다:
- 🐦 트위터에 오리지널 콘텐츠 포스팅
- 💬 성격 있는 답글 달기
- 🧠 과거 상호작용 기억하기
- 😊 기분과 감정 표현하기
- 📈 실시간 트렌드 학습하기

### 🍳 데모 페르소나: 최강록 셰프

넷플릭스 "흑백요리사"에서 영감을 받은 **최강록 셰프** 페르소나가 예시로 포함되어 있습니다.

> **실제 동작 확인**: [@ChoigangrokV](https://twitter.com/ChoigangrokV)

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 🎭 **멀티 페르소나** | YAML 설정으로 성격 교체 |
| 🧠 **3계층 지능** | 핵심 정체성 + 학습된 관심사 + 실시간 트렌드 |
| 💾 **동적 메모리** | 경험 → 영감 → 장기 기억 |
| 🎲 **인간적 행동** | 기분 변동, 피로도, 성격 특성 |
| 🔌 **플랫폼 독립** | 어댑터 패턴으로 플랫폼 교체 용이 |
| 🔄 **독립 행동** | 좋아요/리포스트/댓글 개별 확률 |

---

## 🚀 빠른 시작

```bash
# 클론
git clone https://github.com/YOUR_USERNAME/virtual.git
cd virtual

# 설치
pip install -r requirements.txt

# 설정
cp .env.example .env
# .env에 API 키 입력 (아래 설정 섹션 참고)

# 데모 페르소나 실행 (최강록 셰프)
python main.py

# 또는 나만의 페르소나 실행
PERSONA_NAME=my_persona python main.py
```

---

## 🎨 나만의 페르소나 만들기

```bash
# 1. 템플릿 복사
cp -r personas/_template personas/my_persona

# 2. 정체성 수정
nano personas/my_persona/identity.yaml
```

**identity.yaml** 예시:
```yaml
name: "마이봇"
role: "친근한 AI 어시스턴트"
personality:
  - 호기심 많은
  - 도움을 주는
  - 위트 있는
core_topics:
  - 기술
  - 생산성
  - AI 트렌드
```

```bash
# 3. 실행!
PERSONA_NAME=my_persona python main.py
```

---

## 🔧 설정

### 필수 환경변수

```env
# LLM (Gemini 권장)
GEMINI_API_KEY=your_gemini_key

# Twitter 인증 (쿠키 기반)
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CT0=your_ct0_token
```

### Twitter 쿠키 얻기

1. 브라우저에서 twitter.com 로그인
2. 개발자 도구 (F12) → Application → Cookies → twitter.com
3. `auth_token`과 `ct0` 값 복사

또는 헬퍼 스크립트 사용:
```bash
python scripts/manage_cookies.py import cookies.json
```

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                      SocialAgent                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   Scout     │→ │   Perceive  │→ │   Decide/Act    │ │
│  │  (검색)     │  │ (LLM 분석)  │  │  (행동 결정)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
           │               │               │
           ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Memory   │   │  Persona  │   │  Platform │
    │ (SQLite+  │   │  (YAML)   │   │ (Twitter) │
    │  Vector)  │   │           │   │           │
    └───────────┘   └───────────┘   └───────────┘
```

---

## 📁 프로젝트 구조

```
virtual/
├── agent/                    # 핵심 에이전트 로직
│   ├── bot.py               # 메인 워크플로우
│   ├── memory/              # 메모리 시스템
│   └── platforms/twitter/   # Twitter 어댑터
│
├── personas/                # 🎭 페르소나 설정
│   ├── _template/          # 여기서 시작!
│   └── chef_choi/          # 데모: 최강록 셰프
│
├── scripts/
│   └── manage_cookies.py   # 쿠키 헬퍼
│
└── docs/                    # 문서
```

---

## 🎭 멀티 페르소나 배포

한 PC에서 여러 페르소나 실행:

```bash
# 터미널 1
PERSONA_NAME=chef_choi python main.py

# 터미널 2 (다른 트위터 계정)
PERSONA_NAME=my_bot \
TWITTER_AUTH_TOKEN="other_token" \
TWITTER_CT0="other_ct0" \
python main.py
```

---

## 📊 실행 모드

| 모드 | 설명 |
|------|------|
| `normal` | 일반 (수면 스케줄 적용) |
| `aggressive` | 최대 활동, 휴식 없음 |

```bash
AGENT_MODE=aggressive python main.py
```

---

## ⚠️ 플랫폼 공지

이 프로젝트는 `twikit` (비공식 Twitter 라이브러리)를 사용합니다. Twitter 내부 API 변경 시 동작이 중단될 수 있습니다. **어댑터 패턴**을 사용해 영향을 최소화했으며, Playwright나 공식 API로 교체 시 어댑터만 수정하면 됩니다.

---

## 📚 문서

- [배포 가이드](./docs/DEPLOYMENT_STRATEGY.md)
- [메모리 시스템](./docs/MEMORY_SYSTEM_DESIGN.md)
- [변경 로그](./docs/CHANGELOG_20260120.md)

---

## 🤝 기여하기

1. 이 저장소 Fork
2. `personas/`에 나만의 페르소나 만들기
3. 설정 공유하기 (원하시면!)

---

## 📄 라이선스

MIT License - [LICENSE](./LICENSE) 참조

---

## ⚠️ 면책 조항

이 프로젝트는 교육 목적입니다. 책임감 있게 사용하고 Twitter 이용약관을 준수하세요. 오용이나 계정 정지에 대해 저자는 책임지지 않습니다.

**최강록 셰프 페르소나**는 넷플릭스 "흑백요리사"에서 영감을 받은 팬메이드 트리뷰트입니다. 저작권 침해 의도가 없습니다.
