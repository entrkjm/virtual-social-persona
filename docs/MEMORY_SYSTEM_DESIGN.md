# Memory System Design: 동적 기억 시스템

## 1. Overview

사람의 기억 구조를 모방한 다층 메모리 시스템. 경험이 쌓이고, 강화되고, 잊혀지고, 핵심만 장기 기억으로 남는다.

```
경험 (트윗, 상호작용)
    ↓
Ephemeral Memory (수천 개, 빠른 감쇠)
    ↓ [강화/임팩트]
Short-term Memory (~100개)
    ↓ [반복 강화]
Long-term Memory (~50개)
    ↓ [핵심화]
Core Memory (~20개, 페르소나 통합)
```

---

## 2. Embedding API 선택

| 옵션 | 비용 | 품질 | 비고 |
|-----|------|------|------|
| **Gemini Embedding** | 무료 (1500 req/min) | 좋음 | 이미 Gemini 사용 중 |
| OpenAI text-embedding-3-small | $0.02/1M tokens | 매우 좋음 | |
| Cohere embed-v3 | 무료 (100 req/min) | 좋음 | |
| Voyage AI | 무료 (50M tokens/mo) | 좋음 | |
| sentence-transformers (로컬) | 무료 | 보통 | 추가 리소스 |

**추천: Gemini Embedding API**
- 이미 Gemini API 키 있음
- 무료 티어 넉넉함 (1500 req/min)
- 한국어 지원 좋음

```python
import google.generativeai as genai

def get_embedding(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text
    )
    return result['embedding']  # 768 dimensions
```

---

## 3. 데이터 구조

### 3.1 SQLite 스키마 (구조화 데이터)

```sql
-- 에피소드 기억 (모든 경험의 원본)
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT NOT NULL,              -- 'saw_tweet', 'replied', 'liked', 'posted', 'searched'
    source_id TEXT,                  -- 트윗 ID 등
    source_user TEXT,                -- @handle
    content TEXT NOT NULL,           -- 원본 내용

    -- 분석 결과 (Perceive 단계에서)
    topics TEXT,                     -- JSON array
    sentiment TEXT,                  -- 'positive', 'neutral', 'negative'
    emotional_impact REAL DEFAULT 0.5,  -- 0.0 ~ 1.0

    -- 인덱싱
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 영감 저장소 (글감)
CREATE TABLE inspirations (
    id TEXT PRIMARY KEY,
    episode_id TEXT,                 -- 어떤 경험에서 비롯됐나

    -- 내용
    trigger_content TEXT,            -- 원본 (뭘 보고 영감 받았나)
    topic TEXT,                      -- 핵심 주제
    my_angle TEXT,                   -- 내 관점/해석
    potential_post TEXT,             -- LLM이 생성한 글 초안 (optional)

    -- 동적 속성
    tier TEXT DEFAULT 'ephemeral',   -- 'ephemeral', 'short_term', 'long_term', 'core'
    strength REAL DEFAULT 0.5,       -- 현재 강도
    emotional_impact REAL DEFAULT 0.5,
    reinforcement_count INTEGER DEFAULT 0,

    -- 시간
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_reinforced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at DATETIME,

    -- 사용 여부
    used_count INTEGER DEFAULT 0,
    last_used_at DATETIME,

    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

-- 관계 기억
CREATE TABLE relationships (
    user_handle TEXT PRIMARY KEY,

    -- 기본 정보
    first_met_at DATETIME,
    predefined_relationship TEXT,    -- YAML에서 로드된 사전 정의

    -- 동적 추적
    interaction_count INTEGER DEFAULT 0,
    my_reply_count INTEGER DEFAULT 0,
    their_reply_count INTEGER DEFAULT 0,
    like_given_count INTEGER DEFAULT 0,
    like_received_count INTEGER DEFAULT 0,

    -- 감정/주제
    sentiment_history TEXT,          -- JSON array of recent sentiments
    sentiment_avg REAL DEFAULT 0.0,  -- -1.0 ~ 1.0
    common_topics TEXT,              -- JSON array

    -- 시간
    last_interaction_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 장기 지식 (학습된 사실)
CREATE TABLE knowledge (
    id TEXT PRIMARY KEY,

    subject_type TEXT,               -- 'user', 'topic', 'general'
    subject TEXT,                    -- '@user' or 'topic:파스타'
    fact TEXT NOT NULL,

    confidence REAL DEFAULT 0.5,
    source_episode_id TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reinforcement_count INTEGER DEFAULT 0,

    FOREIGN KEY (source_episode_id) REFERENCES episodes(id)
);

-- Core 기억 (페르소나 확장)
CREATE TABLE core_memories (
    id TEXT PRIMARY KEY,

    type TEXT,                       -- 'obsession', 'opinion', 'theme', 'trait'
    content TEXT NOT NULL,

    -- 형성 과정
    formed_from_inspiration_id TEXT,
    total_reinforcements INTEGER,

    -- 페르소나 영향
    persona_impact TEXT,             -- 어떻게 행동에 영향 주는지

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (formed_from_inspiration_id) REFERENCES inspirations(id)
);

-- 인덱스
CREATE INDEX idx_episodes_timestamp ON episodes(timestamp);
CREATE INDEX idx_inspirations_tier ON inspirations(tier);
CREATE INDEX idx_inspirations_strength ON inspirations(strength);
CREATE INDEX idx_relationships_last_interaction ON relationships(last_interaction_at);
```

### 3.2 Chroma 컬렉션 (벡터 검색)

```python
# 컬렉션 구조
collections = {
    "episodes": {
        # 모든 경험의 임베딩
        "documents": ["트윗 내용", ...],
        "metadatas": [{"type": "saw_tweet", "emotional_impact": 0.7, ...}],
        "ids": ["ep_001", ...]
    },
    "inspirations": {
        # 영감의 임베딩 (trigger_content + my_angle)
        "documents": ["파스타 면의 식감은 시간 싸움 | 알덴테의 진짜 의미", ...],
        "metadatas": [{"tier": "short_term", "strength": 0.6, ...}],
        "ids": ["insp_001", ...]
    }
}
```

---

## 4. 메모리 계층

### 4.1 티어 정의

| 티어 | 진입 조건 | 감쇠율 | 최대 개수 | 수명 |
|-----|----------|--------|----------|------|
| **Ephemeral** | 새로 생성 | 하루 -30% | 무제한 | 수 시간 |
| **Short-term** | strength > 0.3 | 하루 -10% | 100개 | 수 일 |
| **Long-term** | reinforcement >= 3 | 하루 -2% | 50개 | 수 주 |
| **Core** | reinforcement >= 10 | 감쇠 없음 | 20개 | 영구 |

### 4.2 승격/강등 로직

```python
class MemoryTierManager:
    TIER_CONFIG = {
        'ephemeral': {
            'decay_rate': 0.7,      # 하루에 30% 감쇠
            'promotion_threshold': 0.3,
            'demotion_threshold': 0.05,
            'max_count': None
        },
        'short_term': {
            'decay_rate': 0.9,
            'promotion_threshold': None,  # reinforcement 기반
            'promotion_reinforcement': 3,
            'demotion_threshold': 0.1,
            'max_count': 100
        },
        'long_term': {
            'decay_rate': 0.98,
            'promotion_reinforcement': 10,
            'demotion_threshold': 0.2,
            'max_count': 50
        },
        'core': {
            'decay_rate': 1.0,      # 감쇠 없음
            'max_count': 20
        }
    }

    def promote(self, insp: Inspiration) -> bool:
        """승격 시도"""
        current_tier = insp.tier

        if current_tier == 'ephemeral' and insp.strength > 0.3:
            insp.tier = 'short_term'
            return True

        if current_tier == 'short_term' and insp.reinforcement_count >= 3:
            insp.tier = 'long_term'
            return True

        if current_tier == 'long_term' and insp.reinforcement_count >= 10:
            insp.tier = 'core'
            self._integrate_to_persona(insp)
            return True

        return False

    def demote_or_delete(self, insp: Inspiration) -> str:
        """강등 또는 삭제"""
        threshold = self.TIER_CONFIG[insp.tier]['demotion_threshold']

        if insp.strength < threshold:
            if insp.tier == 'ephemeral':
                return 'delete'
            else:
                # 한 단계 강등
                tiers = ['ephemeral', 'short_term', 'long_term', 'core']
                current_idx = tiers.index(insp.tier)
                insp.tier = tiers[current_idx - 1]
                return 'demoted'

        return 'keep'
```

### 4.3 강도 계산

```python
def calculate_strength(self, insp: Inspiration) -> float:
    """현재 시점의 실제 강도 계산"""

    # 기본 감쇠
    hours_since = (datetime.now() - insp.last_reinforced_at).total_seconds() / 3600
    days_since = hours_since / 24

    decay_rate = self.TIER_CONFIG[insp.tier]['decay_rate']
    time_decay = decay_rate ** days_since

    # 감정적 임팩트가 높으면 감쇠 느림
    emotional_factor = 1 - (insp.emotional_impact * 0.3)  # 최대 30% 감쇠 감소
    adjusted_decay = time_decay ** emotional_factor

    # 강화 횟수 많으면 감쇠 느림
    reinforcement_factor = 1 / (1 + insp.reinforcement_count * 0.1)
    adjusted_decay = adjusted_decay ** reinforcement_factor

    return insp.strength * adjusted_decay
```

---

## 5. 강화(Reinforcement) 시스템

### 5.1 강화 트리거

| 이벤트 | 강화량 | 설명 |
|-------|-------|------|
| 비슷한 내용 봄 | +0.1, count +1 | 유사도 > 0.7 |
| 같은 주제 검색 | +0.05, count +1 | 키워드 매칭 |
| 이 영감으로 글 씀 | +0.3, count +3 | 실제 사용 |
| 글 쓰려다 멈춤 | +0.1, count +1 | 의식적 접근 |
| 타인이 비슷한 주제 언급 | +0.05 | 외부 강화 |

### 5.2 강화 로직

```python
class ReinforcementEngine:
    def on_content_seen(self, new_content: str, emotional_impact: float):
        """새 콘텐츠를 봤을 때"""

        # 1. 유사한 영감 검색
        similar = self.chroma.query(
            query_texts=[new_content],
            n_results=5,
            where={"strength": {"$gt": 0.1}}
        )

        for match in similar['matches']:
            if match['distance'] < 0.3:  # 유사도 높음
                insp = self.get_inspiration(match['id'])
                self._reinforce(insp, amount=0.1, count=1)

                # Flash 판단: 비슷한 거 또 보는데 임팩트도 높다?
                if emotional_impact > 0.8 and insp.strength > 0.5:
                    return InspirationTrigger(
                        type='flash_reinforced',
                        inspiration=insp,
                        reason='관심사에 또 자극받음'
                    )

        return None

    def on_posted(self, inspiration_id: str):
        """영감을 사용해서 글을 썼을 때"""
        insp = self.get_inspiration(inspiration_id)

        self._reinforce(insp, amount=0.3, count=3)
        insp.used_count += 1
        insp.last_used_at = datetime.now()

        # 최소 long_term 보장
        if insp.tier in ['ephemeral', 'short_term']:
            insp.tier = 'long_term'

    def _reinforce(self, insp: Inspiration, amount: float, count: int):
        insp.strength = min(1.0, insp.strength + amount)
        insp.reinforcement_count += count
        insp.last_reinforced_at = datetime.now()

        # 승격 체크
        self.tier_manager.promote(insp)
```

---

## 6. 정리(Consolidation) 시스템

```python
class MemoryConsolidator:
    """주기적으로 실행 (매 시간)"""

    def run(self):
        stats = {'deleted': 0, 'demoted': 0, 'promoted': 0}

        for insp in self.all_inspirations():
            # 1. 현재 강도 계산
            current_strength = self.calculate_strength(insp)
            insp.strength = current_strength

            # 2. 강등/삭제 체크
            action = self.tier_manager.demote_or_delete(insp)
            if action == 'delete':
                self.delete_inspiration(insp)
                stats['deleted'] += 1
            elif action == 'demoted':
                stats['demoted'] += 1

            # 3. 승격 체크
            if self.tier_manager.promote(insp):
                stats['promoted'] += 1

        # 4. 티어별 개수 제한 적용
        self._enforce_tier_limits()

        # 5. Chroma 메타데이터 동기화
        self._sync_chroma_metadata()

        return stats

    def _enforce_tier_limits(self):
        """티어별 최대 개수 초과 시 약한 것부터 강등"""
        for tier, config in self.TIER_CONFIG.items():
            max_count = config.get('max_count')
            if max_count is None:
                continue

            inspirations = self.get_by_tier(tier, order_by='strength ASC')

            if len(inspirations) > max_count:
                excess = inspirations[:len(inspirations) - max_count]
                for insp in excess:
                    self.tier_manager.demote_or_delete(insp)
```

---

## 7. 글쓰기(Posting) 트리거

### 7.1 트리거 타입

| 타입 | 조건 | 확률 |
|-----|------|------|
| **Flash** | 방금 본 게 impact > 0.9 | 70% |
| **Flash Reinforced** | 관심사 또 봄 + impact > 0.8 | 80% |
| **Ready** | long_term 이상 + 숙성 24h+ | 기본 체크 |
| **Mood Burst** | mood > 0.8 + ready 영감 있음 | 30% |
| **Random Recall** | 그냥 갑자기 생각남 | 5% |

### 7.2 트리거 로직

```python
class PostingTriggerEngine:
    def check_trigger(self, context: dict) -> Optional[PostingDecision]:
        """매 step마다 호출"""

        # 빈도 제한 체크
        if not self._can_post_now():
            return None

        # 1. Flash - 방금 본 게 너무 인상적
        if context.get('current_episode'):
            ep = context['current_episode']
            if ep.emotional_impact >= 0.9:
                if random.random() < 0.7:
                    return PostingDecision(
                        type='flash',
                        source=ep,
                        urgency='immediate',
                        reason='필 꽂힘'
                    )

        # 2. Flash Reinforced - 관심사에 또 자극
        if context.get('reinforcement_trigger'):
            trigger = context['reinforcement_trigger']
            if trigger.type == 'flash_reinforced':
                if random.random() < 0.8:
                    return PostingDecision(
                        type='flash_reinforced',
                        source=trigger.inspiration,
                        urgency='immediate',
                        reason=trigger.reason
                    )

        # 3. Ready - 숙성된 영감 발현
        ready_inspirations = self._get_ready_inspirations()
        if ready_inspirations:
            # 비슷한 주제를 방금 봤으면 트리거
            if context.get('current_episode'):
                for insp in ready_inspirations:
                    if self._topic_matches(insp, context['current_episode']):
                        return PostingDecision(
                            type='triggered',
                            source=insp,
                            urgency='soon',
                            reason=f"'{insp.topic}' 관련 또 봄"
                        )

        # 4. Mood Burst - 기분 좋아서
        if self.behavior_engine.current_mood >= 0.8:
            if ready_inspirations and random.random() < 0.3:
                return PostingDecision(
                    type='mood_burst',
                    source=random.choice(ready_inspirations),
                    urgency='soon',
                    reason='기분 좋아서 글 쓰고 싶음'
                )

        # 5. Random Recall - 갑자기 생각남
        if ready_inspirations and random.random() < 0.05:
            return PostingDecision(
                type='random_recall',
                source=random.choice(ready_inspirations),
                urgency='whenever',
                reason='갑자기 생각남'
            )

        return None

    def _can_post_now(self) -> bool:
        """빈도 제한 체크"""
        today_posts = self.db.count_posts_today()
        if today_posts >= 5:  # 하루 최대 5개
            return False

        last_post = self.db.get_last_post_time()
        if last_post:
            minutes_since = (datetime.now() - last_post).seconds / 60
            if minutes_since < 60:  # 최소 1시간 간격
                return False

        return True

    def _get_ready_inspirations(self) -> list[Inspiration]:
        """발현 준비된 영감들"""
        return self.db.query("""
            SELECT * FROM inspirations
            WHERE tier IN ('long_term', 'core')
            AND strength > 0.4
            AND (used_count = 0 OR last_used_at < datetime('now', '-7 days'))
            AND created_at < datetime('now', '-1 day')
            ORDER BY strength DESC
            LIMIT 10
        """)
```

---

## 8. Core Memory → 페르소나 통합

```python
class PersonaIntegrator:
    def integrate_core_memory(self, insp: Inspiration):
        """Core로 승격된 영감을 페르소나에 반영"""

        # 1. Core 유형 판단
        core_type = self._classify_core_type(insp)

        # 2. core_memories 테이블에 저장
        core = CoreMemory(
            id=generate_id(),
            type=core_type,
            content=insp.my_angle,
            formed_from_inspiration_id=insp.id,
            total_reinforcements=insp.reinforcement_count
        )

        # 3. 페르소나 영향 정의
        if core_type == 'obsession':
            core.persona_impact = f"'{insp.topic}'에 대해 자주 언급하고 관심 보임"
        elif core_type == 'opinion':
            core.persona_impact = f"'{insp.topic}'에 대해 특정 입장을 가짐"
        elif core_type == 'theme':
            core.persona_impact = f"대화/글에서 '{insp.topic}' 테마가 자주 등장"

        self.db.save(core)

        # 4. 동적 페르소나 YAML 업데이트 (optional)
        self._update_persona_yaml(core)

    def get_core_context_for_llm(self) -> str:
        """LLM 프롬프트에 주입할 Core 기억 컨텍스트"""
        cores = self.db.get_all_core_memories()

        if not cores:
            return ""

        context = "### 🧠 CORE MEMORIES (장기 기억):\n"

        obsessions = [c for c in cores if c.type == 'obsession']
        if obsessions:
            context += "**집착하는 주제**: " + ", ".join([c.content for c in obsessions]) + "\n"

        opinions = [c for c in cores if c.type == 'opinion']
        if opinions:
            context += "**확고한 의견**: " + ", ".join([c.content for c in opinions]) + "\n"

        themes = [c for c in cores if c.type == 'theme']
        if themes:
            context += "**반복 테마**: " + ", ".join([c.content for c in themes]) + "\n"

        return context
```

---

## 9. 파일 구조

```
agent/
├── memory/
│   ├── __init__.py
│   ├── database.py          # SQLite 연결 및 쿼리
│   ├── vector_store.py      # Chroma + Gemini Embedding
│   ├── episode_memory.py    # 에피소드 기억 관리
│   ├── inspiration_pool.py  # 영감 저장소
│   ├── relationship_memory.py  # 관계 기억
│   ├── tier_manager.py      # 티어 승격/강등
│   ├── consolidator.py      # 정리 (주기 실행)
│   ├── reinforcement.py     # 강화 엔진
│   └── persona_integrator.py  # Core → 페르소나
├── posting/
│   ├── __init__.py
│   ├── trigger_engine.py    # 글쓰기 트리거
│   └── post_generator.py    # 영감 → 글 생성
└── behavior_engine.py       # 기존 (수정)
```

---

## 10. 구현 순서

| Phase | 내용 | 예상 복잡도 |
|-------|------|-----------|
| **1** | SQLite 스키마 + 마이그레이션 | 중 |
| **2** | Chroma + Gemini Embedding 설정 | 중 |
| **3** | Episode/Inspiration 기본 CRUD | 낮음 |
| **4** | 티어 시스템 + 강도 계산 | 중 |
| **5** | 강화 엔진 | 중 |
| **6** | 정리(Consolidation) 스케줄러 | 중 |
| **7** | 글쓰기 트리거 | 중 |
| **8** | bot.py 통합 | 중 |
| **9** | Core → 페르소나 통합 | 높음 |
| **10** | 기존 JSON 데이터 마이그레이션 | 낮음 |

---

## 11. 의존성

```
# requirements.txt 추가
chromadb>=0.4.0
google-generativeai>=0.3.0  # 이미 있음
```

---

## 12. 설정 (behavior.yaml 확장)

```yaml
# config/personas/chef_choi_behavior.yaml에 추가

memory_config:
  # 티어 설정
  tiers:
    ephemeral:
      decay_rate_per_day: 0.7
      max_count: null
    short_term:
      decay_rate_per_day: 0.9
      promotion_threshold_strength: 0.3
      max_count: 100
    long_term:
      decay_rate_per_day: 0.98
      promotion_threshold_reinforcement: 3
      max_count: 50
    core:
      decay_rate_per_day: 1.0
      promotion_threshold_reinforcement: 10
      max_count: 20

  # 정리 주기
  consolidation:
    interval_hours: 1

  # 강화 설정
  reinforcement:
    similar_content_seen: 0.1
    same_topic_searched: 0.05
    posted_about: 0.3
    similarity_threshold: 0.7

posting_config:
  max_posts_per_day: 5
  min_interval_minutes: 60

  triggers:
    flash:
      impact_threshold: 0.9
      probability: 0.7
    flash_reinforced:
      impact_threshold: 0.8
      probability: 0.8
    mood_burst:
      mood_threshold: 0.8
      probability: 0.3
    random_recall:
      probability: 0.05
```
