# Agent Behavior Configuration Guide
에이전트 행동 설정 가이드

## 설정 위치
`.env` 파일에 추가하거나, 실행 시 환경변수로 전달.

## 단위 요약

| 설정 | 단위 | 기본값 |
|-----|------|--------|
| `STEP_INTERVAL_MIN/MAX` | **초** | 30 / 300 |
| `POST_MIN_INTERVAL` | **분** | 60 |
| `CONSOLIDATION_INTERVAL` | **시간** | 1 |
| `PROB_*` | **0.0~1.0** | 다양 |

---

## 1. Step 간격 (STEP_INTERVAL)

한 행동 후 다음 행동까지 대기 시간 (초).

| 설정 | 단위 | 설명 |
|-----|------|------|
| `STEP_INTERVAL_MIN` | 초 | 최소 대기 시간 |
| `STEP_INTERVAL_MAX` | 초 | 최대 대기 시간 |

### 권장값

| 모드 | MIN | MAX | 설명 |
|-----|-----|-----|------|
| **테스트** | 5 | 10 | 빠른 동작 확인 |
| **개발** | 30 | 60 | 적당한 속도로 로그 확인 |
| **사람처럼** | 120 | 600 | 2~10분 간격, 자연스러움 |
| **프로덕션** | 180 | 900 | 3~15분, 가장 자연스러움 |

```bash
# 테스트
STEP_INTERVAL_MIN=5
STEP_INTERVAL_MAX=10

# 프로덕션 (사람처럼)
STEP_INTERVAL_MIN=180
STEP_INTERVAL_MAX=900
```

---

## 2. 행동 확률 (Action Probability)

트윗을 봤을 때 어떤 행동을 할지 결정.
**모든 확률의 합이 1.0이 되어야 함.**

| 설정 | 행동 | 설명 |
|-----|------|------|
| `PROB_LURK` | 그냥 넘김 | 아무 행동 안 함 |
| `PROB_LIKE_ONLY` | 좋아요만 | 가벼운 관심 표현 |
| `PROB_COMMENT` | 댓글 | 적극적 참여 |
| `PROB_LIKE_AND_COMMENT` | 좋아요+댓글 | 강한 관심 |

### 권장값

| 모드 | LURK | LIKE | COMMENT | LIKE+COMMENT |
|-----|------|------|---------|--------------|
| **테스트** | 0.10 | 0.30 | 0.50 | 0.10 |
| **내향적 캐릭터** | 0.50 | 0.30 | 0.15 | 0.05 |
| **외향적 캐릭터** | 0.20 | 0.30 | 0.40 | 0.10 |
| **사람처럼 (기본)** | 0.40 | 0.30 | 0.25 | 0.05 |

**내향적 캐릭터 (최강록 셰프):**
- 대부분 조용히 관찰 (LURK 높음)
- 댓글은 정말 꽂힐 때만
- 좋아요는 적당히

```bash
# 내향적 (권장)
PROB_LURK=0.50
PROB_LIKE_ONLY=0.30
PROB_COMMENT=0.15
PROB_LIKE_AND_COMMENT=0.05
```

---

## 3. 현타 확률 (PROB_REGRET)

행동 후 "왜 이랬지..." 하고 후회하는 확률.
높을수록 같은 포스트/유저에게 연속 반응 안 함.

| 값 | 효과 |
|---|------|
| 0.1 | 거의 후회 안 함, 적극적 |
| 0.3 | 가끔 후회, 자연스러움 (기본) |
| 0.5 | 자주 후회, 소극적 |
| 0.7 | 매우 소극적, 거의 한번만 반응 |

```bash
# 내향적 캐릭터
PROB_REGRET=0.40

# 외향적 캐릭터
PROB_REGRET=0.15
```

---

## 4. 포스팅 트리거 확률

독립적인 글을 올릴 확률. 조건 충족 시 이 확률로 결정.

| 설정 | 트리거 | 설명 |
|-----|--------|------|
| `PROB_FLASH` | 즉각 영감 | 강하게 꽂혔을 때 |
| `PROB_FLASH_REINFORCED` | 반복 자극 | 비슷한 거 또 봤을 때 |
| `PROB_MOOD_BURST` | 기분 폭발 | 무드가 극단으로 갔을 때 |
| `PROB_RANDOM_RECALL` | 랜덤 회상 | 갑자기 생각나서 |

### 권장값

| 모드 | FLASH | REINFORCED | MOOD | RANDOM |
|-----|-------|------------|------|--------|
| **테스트** | 0.90 | 0.90 | 0.50 | 0.20 |
| **활발한 계정** | 0.80 | 0.85 | 0.40 | 0.10 |
| **사람처럼** | 0.70 | 0.80 | 0.30 | 0.05 |
| **조용한 계정** | 0.50 | 0.60 | 0.20 | 0.02 |

```bash
# 사람처럼 (기본)
PROB_FLASH=0.70
PROB_FLASH_REINFORCED=0.80
PROB_MOOD_BURST=0.30
PROB_RANDOM_RECALL=0.05
```

---

## 5. 포스팅 간격 (POST_MIN_INTERVAL)

글 올린 후 최소 대기 시간. **단위: 분**
너무 자주 올리면 스팸처럼 보임.

| 값 | 설명 |
|--------|------|
| 5 | 테스트용 |
| 30 | 활발한 계정 |
| 60 | 일반적 (기본) |
| 120 | 조용한 계정 |
| 240 | 매우 조용함 |

```bash
# 테스트
POST_MIN_INTERVAL=5

# 프로덕션
POST_MIN_INTERVAL=60
```

---

## 6. Memory Consolidation 간격 (CONSOLIDATION_INTERVAL)

메모리 정리 주기. **단위: 시간**. 낮을수록 자주 정리.

| 값 | 설명 |
|---|------|
| 1 | 1시간마다 (기본) |
| 6 | 6시간마다 |
| 24 | 하루에 한번 |

```bash
CONSOLIDATION_INTERVAL=1
```

---

## 프리셋 모음

### 테스트 모드 (빠른 확인)
```bash
STEP_INTERVAL_MIN=5
STEP_INTERVAL_MAX=10
PROB_LURK=0.10
PROB_LIKE_ONLY=0.30
PROB_COMMENT=0.50
PROB_LIKE_AND_COMMENT=0.10
PROB_REGRET=0.10
PROB_FLASH=0.90
PROB_FLASH_REINFORCED=0.90
PROB_MOOD_BURST=0.50
PROB_RANDOM_RECALL=0.20
POST_MIN_INTERVAL=5
CONSOLIDATION_INTERVAL=1
```

### 내향적 캐릭터 (최강록 셰프)
```bash
STEP_INTERVAL_MIN=180
STEP_INTERVAL_MAX=600
PROB_LURK=0.50
PROB_LIKE_ONLY=0.30
PROB_COMMENT=0.15
PROB_LIKE_AND_COMMENT=0.05
PROB_REGRET=0.40
PROB_FLASH=0.60
PROB_FLASH_REINFORCED=0.75
PROB_MOOD_BURST=0.25
PROB_RANDOM_RECALL=0.03
POST_MIN_INTERVAL=90
CONSOLIDATION_INTERVAL=2
```

### 외향적 캐릭터
```bash
STEP_INTERVAL_MIN=60
STEP_INTERVAL_MAX=300
PROB_LURK=0.20
PROB_LIKE_ONLY=0.25
PROB_COMMENT=0.40
PROB_LIKE_AND_COMMENT=0.15
PROB_REGRET=0.15
PROB_FLASH=0.85
PROB_FLASH_REINFORCED=0.90
PROB_MOOD_BURST=0.45
PROB_RANDOM_RECALL=0.10
POST_MIN_INTERVAL=30
CONSOLIDATION_INTERVAL=1
```

### 프로덕션 (사람처럼, 균형)
```bash
STEP_INTERVAL_MIN=120
STEP_INTERVAL_MAX=480
PROB_LURK=0.40
PROB_LIKE_ONLY=0.30
PROB_COMMENT=0.25
PROB_LIKE_AND_COMMENT=0.05
PROB_REGRET=0.30
PROB_FLASH=0.70
PROB_FLASH_REINFORCED=0.80
PROB_MOOD_BURST=0.30
PROB_RANDOM_RECALL=0.05
POST_MIN_INTERVAL=60
CONSOLIDATION_INTERVAL=1
```

---

## 실행 예시

```bash
# .env 파일 수정 후 실행
python -u main.py

# 또는 환경변수로 직접 전달 (테스트)
STEP_INTERVAL_MIN=5 STEP_INTERVAL_MAX=10 python -u main.py

# 여러 값 한번에
STEP_INTERVAL_MIN=5 STEP_INTERVAL_MAX=10 PROB_COMMENT=0.80 python -u main.py
```

---

## 주의사항

1. **확률 합계**: `PROB_LURK + PROB_LIKE_ONLY + PROB_COMMENT + PROB_LIKE_AND_COMMENT = 1.0`
2. **너무 빠른 간격**: 트위터 rate limit 걸릴 수 있음
3. **너무 높은 포스팅 확률**: 스팸처럼 보일 수 있음
4. **캐릭터 일관성**: 페르소나와 맞는 설정 사용
