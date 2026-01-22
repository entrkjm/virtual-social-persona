# Deployment Guide: Home PC Multi-Bot Setup

## Overview
집 PC에서 3개 봇을 운영하는 최소 구성 가이드.

---

## 1. Cookie Management

### 현재 쿠키 확인
```bash
python scripts/manage_cookies.py show
```

### 브라우저에서 쿠키 가져오기
1. 브라우저에서 twitter.com 로그인
2. "EditThisCookie" 확장 → Export (JSON)
3. 변환:
```bash
python scripts/manage_cookies.py import cookies.json
```

### 다른 계정용 쿠키 관리
```bash
# 클라이언트 A 전용 .env에 저장
python scripts/manage_cookies.py import client_a_cookies.json --env-file personas/client_a/.env
```

---

## 2. Multi-Persona 실행

### 환경변수로 페르소나 선택
```bash
# 환경변수로 페르소나 지정
PERSONA_NAME=chef_choi python main.py

# 다른 계정 실행 시
# 1. data/cookies/client_a_cookies.json 생성
# 2. 실행
PERSONA_NAME=client_a python main.py
```

### Screen으로 백그라운드 실행 (추천)
```bash
# 터미널 1 - Chef Choi
screen -S chef
PERSONA_NAME=chef_choi python main.py
# Ctrl+A, D → detach

# 터미널 2 - Client A (쿠키 파일 미리 준비)
screen -S client_a
PERSONA_NAME=client_a python main.py
# Ctrl+A, D → detach

# 세션 확인
screen -ls

# 다시 연결
screen -r chef
```

---

## 3. 새 페르소나 추가

```bash
# 1. 기존 페르소나 복사
cp -r personas/chef_choi personas/new_persona

# 2. identity.yaml 수정
code personas/new_persona/identity.yaml

# 3. (선택) 전용 쿠키 파일
python scripts/manage_cookies.py import cookies.json --env-file personas/new_persona/.env
```

---

## 4. IP 관련 참고사항

| 상황 | 리스크 |
|---|---|
| 같은 IP에서 3개 계정 독립 활동 | ✅ 낮음 (가족/회사처럼 보임) |
| 같은 IP에서 계정끼리 상호작용 | 🚨 높음 (연좌제 가능) |
| 데이터센터 IP (AWS/GCP) | ⚠️ 중간 (프록시 권장) |

**현재 설정**: 집 PC → 같은 IP → 상호작용 안 하면 OK

---

## 5. Twikit 지속가능성

`twikit`은 비공식 라이브러리로, 언제든 작동 중단 가능.

**우리 코드의 대비책**:
- `TwitterAdapter`가 `twikit` 사용을 완전히 캡슐화
- `bot.py`에서는 `twikit` 직접 참조 없음
- 추후 `PlaywrightAdapter`로 교체 시 `bot.py` 수정 불필요

---

## Troubleshooting

| 증상 | 해결 |
|---|---|
| `401 Unauthorized` | 쿠키 만료 → 브라우저에서 재로그인 후 `import` |
| `429 Too Many Requests` | 5분 대기 후 재시도 |
| 페르소나 로드 실패 | `PERSONA_NAME` 오타 확인, `personas/` 폴더 존재 확인 |
