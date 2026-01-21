"""
Memory Database
SQLite 기반 구조화 데이터 저장소
Structured data storage with SQLite
"""
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from config.settings import settings


@dataclass
class Episode:
    id: str
    timestamp: datetime
    type: str  # 'saw_tweet', 'replied', 'liked', 'posted', 'searched'
    source_id: Optional[str]
    source_user: Optional[str]
    content: str
    topics: List[str]
    sentiment: str
    emotional_impact: float


@dataclass
class Inspiration:
    id: str
    episode_id: Optional[str]
    trigger_content: str
    topic: str
    my_angle: str
    potential_post: Optional[str]
    tier: str  # 'ephemeral', 'short_term', 'long_term', 'core'
    strength: float
    emotional_impact: float
    reinforcement_count: int
    created_at: datetime
    last_reinforced_at: datetime
    last_accessed_at: Optional[datetime]
    used_count: int
    last_used_at: Optional[datetime]


@dataclass
class Relationship:
    user_handle: str
    first_met_at: Optional[datetime]
    predefined_relationship: Optional[str]
    interaction_count: int
    my_reply_count: int
    their_reply_count: int
    like_given_count: int
    like_received_count: int
    sentiment_history: List[str]
    sentiment_avg: float
    common_topics: List[str]
    last_interaction_at: Optional[datetime]


@dataclass
class CoreMemory:
    id: str
    type: str  # 'obsession', 'opinion', 'theme', 'trait'
    content: str
    formed_from_inspiration_id: Optional[str]
    total_reinforcements: int
    persona_impact: Optional[str]
    created_at: datetime


@dataclass
class PersonMemory:
    """사람에 대한 기억 / Memory about a person"""
    user_id: str
    platform: str
    screen_name: str
    who_is_this: str  # 자연어 설명 (LLM이 업데이트)
    tier: str  # 'stranger', 'acquaintance', 'familiar', 'friend'
    affinity: float  # -1.0 ~ 1.0
    memorable_moments: List[Dict[str, Any]]  # [{date, summary}]
    latest_conversations: List[Dict[str, Any]]  # [{id, date, type, post_id, topic, summary, turns, state}]
    first_met_at: datetime
    last_interaction_at: Optional[datetime]
    updated_at: datetime


@dataclass
class ConversationRecord:
    """대화 기록 / Conversation record"""
    id: str
    person_id: str  # PersonMemory.user_id
    platform: str
    post_id: str
    conversation_type: str  # 'my_post_reply', 'their_post_reply', 'mention', 'quote', 'dm'
    topic: Optional[str]
    summary: str  # LLM이 생성한 요약
    turn_count: int
    state: str  # 'ongoing', 'concluded', 'stale'
    started_at: datetime
    last_updated_at: datetime


@dataclass
class PostMemory:
    """포스트에 대한 기억 / Memory about a post"""
    post_id: str  # 플랫폼 고유 ID
    platform: str
    author_id: str
    author_screen_name: str
    content_preview: str  # 요약 또는 앞부분 (100자 제한)
    my_reactions: List[str]  # ['like', 'reply', 'repost', 'quote']
    my_reply_id: Optional[str]  # 내가 단 답글 ID (있으면)
    conversation_id: Optional[str]  # 연결된 ConversationRecord ID
    first_seen_at: datetime
    last_interacted_at: Optional[datetime]


class MemoryDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.MEMORY_DB_PATH
        self._ensure_data_dir()
        self._init_db()
        self._migrate_db()  # Add platform columns to existing DBs

    def _ensure_data_dir(self):
        """데이터 디렉토리 생성 / Ensure data directory exists"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Episodes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    platform TEXT DEFAULT 'twitter',
                    type TEXT NOT NULL,
                    source_id TEXT,
                    source_user TEXT,
                    content TEXT NOT NULL,
                    topics TEXT,
                    sentiment TEXT,
                    emotional_impact REAL DEFAULT 0.5,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Inspirations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inspirations (
                    id TEXT PRIMARY KEY,
                    episode_id TEXT,
                    trigger_content TEXT,
                    topic TEXT,
                    my_angle TEXT,
                    potential_post TEXT,
                    tier TEXT DEFAULT 'ephemeral',
                    strength REAL DEFAULT 0.5,
                    emotional_impact REAL DEFAULT 0.5,
                    reinforcement_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_reinforced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed_at DATETIME,
                    used_count INTEGER DEFAULT 0,
                    last_used_at DATETIME,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id)
                )
            """)

            # Relationships table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    user_handle TEXT NOT NULL,
                    platform TEXT DEFAULT 'twitter',
                    first_met_at DATETIME,
                    predefined_relationship TEXT,
                    interaction_count INTEGER DEFAULT 0,
                    my_reply_count INTEGER DEFAULT 0,
                    their_reply_count INTEGER DEFAULT 0,
                    like_given_count INTEGER DEFAULT 0,
                    like_received_count INTEGER DEFAULT 0,
                    sentiment_history TEXT,
                    sentiment_avg REAL DEFAULT 0.0,
                    common_topics TEXT,
                    last_interaction_at DATETIME,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (platform, user_handle)
                )
            """)

            # Knowledge table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id TEXT PRIMARY KEY,
                    subject_type TEXT,
                    subject TEXT,
                    fact TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    source_episode_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reinforcement_count INTEGER DEFAULT 0,
                    FOREIGN KEY (source_episode_id) REFERENCES episodes(id)
                )
            """)

            # Core memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS core_memories (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    content TEXT NOT NULL,
                    formed_from_inspiration_id TEXT,
                    total_reinforcements INTEGER,
                    persona_impact TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (formed_from_inspiration_id) REFERENCES inspirations(id)
                )
            """)

            # Posting history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posting_history (
                    id TEXT PRIMARY KEY,
                    platform TEXT DEFAULT 'twitter',
                    inspiration_id TEXT,
                    content TEXT NOT NULL,
                    trigger_type TEXT,
                    posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (inspiration_id) REFERENCES inspirations(id)
                )
            """)

            # Pattern usage table (말투 패턴 사용 추적)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    post_id TEXT,
                    used_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Person memories table (Social v2)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS person_memories (
                    user_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    screen_name TEXT NOT NULL,
                    who_is_this TEXT,
                    tier TEXT DEFAULT 'stranger',
                    affinity REAL DEFAULT 0.0,
                    memorable_moments TEXT,
                    latest_conversations TEXT,
                    first_met_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_interaction_at DATETIME,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (platform, user_id)
                )
            """)

            # Conversation records table (Social v2)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_records (
                    id TEXT PRIMARY KEY,
                    person_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    conversation_type TEXT NOT NULL,
                    topic TEXT,
                    summary TEXT,
                    turn_count INTEGER DEFAULT 1,
                    state TEXT DEFAULT 'ongoing',
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Post memories table (중복 반응 방지 + 대화 컨텍스트)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS post_memories (
                    post_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    author_screen_name TEXT NOT NULL,
                    content_preview TEXT,
                    my_reactions TEXT,
                    my_reply_id TEXT,
                    conversation_id TEXT,
                    first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_interacted_at DATETIME,
                    PRIMARY KEY (platform, post_id)
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspirations_tier ON inspirations(tier)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspirations_strength ON inspirations(strength)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_last_interaction ON relationships(last_interaction_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_usage_type ON pattern_usage(pattern_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_usage_at ON pattern_usage(used_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_memories_tier ON person_memories(tier)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_memories_affinity ON person_memories(affinity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_records_person ON conversation_records(person_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_records_state ON conversation_records(state)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_post_memories_author ON post_memories(author_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_post_memories_last_interacted ON post_memories(last_interacted_at)")


    def _migrate_db(self):
        """기존 DB에 platform 컬럼 추가 마이그레이션"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if platform column exists in each table
            tables_to_migrate = ['episodes', 'posting_history', 'relationships']
            
            for table in tables_to_migrate:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'platform' not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN platform TEXT DEFAULT 'twitter'")
                        print(f"[DB Migration] Added platform column to {table}")
                    except Exception as e:
                        # Column might already exist (race condition)
                        pass

    # ==================== Episode Methods ====================

    def add_episode(self, episode: Episode) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodes (id, timestamp, type, source_id, source_user, content, topics, sentiment, emotional_impact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode.id,
                episode.timestamp.isoformat(),
                episode.type,
                episode.source_id,
                episode.source_user,
                episode.content,
                json.dumps(episode.topics, ensure_ascii=False),
                episode.sentiment,
                episode.emotional_impact
            ))
        return episode.id

    def get_recent_episodes(self, limit: int = 10, type_filter: Optional[str] = None) -> List[Episode]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if type_filter:
                cursor.execute("""
                    SELECT * FROM episodes WHERE type = ? ORDER BY timestamp DESC LIMIT ?
                """, (type_filter, limit))
            else:
                cursor.execute("""
                    SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            return [self._row_to_episode(row) for row in cursor.fetchall()]

    def _row_to_episode(self, row) -> Episode:
        return Episode(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            type=row['type'],
            source_id=row['source_id'],
            source_user=row['source_user'],
            content=row['content'],
            topics=json.loads(row['topics']) if row['topics'] else [],
            sentiment=row['sentiment'],
            emotional_impact=row['emotional_impact']
        )

    # ==================== Inspiration Methods ====================

    def add_inspiration(self, insp: Inspiration) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inspirations
                (id, episode_id, trigger_content, topic, my_angle, potential_post, tier, strength,
                 emotional_impact, reinforcement_count, created_at, last_reinforced_at, used_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                insp.id,
                insp.episode_id,
                insp.trigger_content,
                insp.topic,
                insp.my_angle,
                insp.potential_post,
                insp.tier,
                insp.strength,
                insp.emotional_impact,
                insp.reinforcement_count,
                insp.created_at.isoformat(),
                insp.last_reinforced_at.isoformat(),
                insp.used_count
            ))
        return insp.id

    def get_inspiration(self, insp_id: str) -> Optional[Inspiration]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inspirations WHERE id = ?", (insp_id,))
            row = cursor.fetchone()
            return self._row_to_inspiration(row) if row else None

    def get_inspiration_by_topic(self, topic: str) -> Optional[Inspiration]:
        """토픽으로 영감 조회 (가장 강한 것)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM inspirations WHERE topic = ?
                ORDER BY strength DESC LIMIT 1
            """, (topic,))
            row = cursor.fetchone()
            return self._row_to_inspiration(row) if row else None

    def get_inspirations_by_tier(self, tier: str, order_by: str = "strength DESC", limit: int = 100) -> List[Inspiration]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM inspirations WHERE tier = ? ORDER BY {order_by} LIMIT ?
            """, (tier, limit))
            return [self._row_to_inspiration(row) for row in cursor.fetchall()]

    def get_ready_inspirations(
        self,
        min_strength: float = 0.4,
        tiers: Optional[List[str]] = None,
        maturation_hours: int = 24,
        cooldown_days: int = 7,
        limit: int = 10
    ) -> List[Inspiration]:
        """발현 준비된 영감들 조회

        Args:
            min_strength: 최소 강도
            tiers: 조회할 티어 목록 (기본: long_term, core)
            maturation_hours: 생성 후 최소 경과 시간
            cooldown_days: 마지막 사용 후 최소 경과 일수
            limit: 최대 결과 수
        """
        if tiers is None:
            tiers = ['long_term', 'core']

        tier_placeholders = ','.join(['?' for _ in tiers])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = f"""
                SELECT * FROM inspirations
                WHERE tier IN ({tier_placeholders})
                AND strength > ?
                AND (used_count = 0 OR last_used_at < datetime('now', '-{cooldown_days} days'))
                AND created_at < datetime('now', '-{maturation_hours} hours')
                ORDER BY strength DESC
                LIMIT ?
            """
            params = list(tiers) + [min_strength, limit]
            cursor.execute(query, params)
            return [self._row_to_inspiration(row) for row in cursor.fetchall()]

    def update_inspiration(self, insp: Inspiration):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE inspirations SET
                    tier = ?, strength = ?, emotional_impact = ?, reinforcement_count = ?,
                    last_reinforced_at = ?, last_accessed_at = ?, used_count = ?, last_used_at = ?,
                    potential_post = ?
                WHERE id = ?
            """, (
                insp.tier,
                insp.strength,
                insp.emotional_impact,
                insp.reinforcement_count,
                insp.last_reinforced_at.isoformat() if insp.last_reinforced_at else None,
                insp.last_accessed_at.isoformat() if insp.last_accessed_at else None,
                insp.used_count,
                insp.last_used_at.isoformat() if insp.last_used_at else None,
                insp.potential_post,
                insp.id
            ))

    def delete_inspiration(self, insp_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inspirations WHERE id = ?", (insp_id,))

    def get_all_inspirations(self) -> List[Inspiration]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inspirations")
            return [self._row_to_inspiration(row) for row in cursor.fetchall()]

    def count_inspirations_by_tier(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tier, COUNT(*) as count FROM inspirations GROUP BY tier
            """)
            return {row['tier']: row['count'] for row in cursor.fetchall()}

    def _row_to_inspiration(self, row) -> Inspiration:
        return Inspiration(
            id=row['id'],
            episode_id=row['episode_id'],
            trigger_content=row['trigger_content'],
            topic=row['topic'],
            my_angle=row['my_angle'],
            potential_post=row['potential_post'],
            tier=row['tier'],
            strength=row['strength'],
            emotional_impact=row['emotional_impact'],
            reinforcement_count=row['reinforcement_count'],
            created_at=datetime.fromisoformat(row['created_at']),
            last_reinforced_at=datetime.fromisoformat(row['last_reinforced_at']) if row['last_reinforced_at'] else datetime.now(),
            last_accessed_at=datetime.fromisoformat(row['last_accessed_at']) if row['last_accessed_at'] else None,
            used_count=row['used_count'],
            last_used_at=datetime.fromisoformat(row['last_used_at']) if row['last_used_at'] else None
        )

    # ==================== Relationship Methods ====================

    def get_or_create_relationship(self, user_handle: str) -> Relationship:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM relationships WHERE user_handle = ?", (user_handle,))
            row = cursor.fetchone()

            if row:
                return self._row_to_relationship(row)

            # Create new
            rel = Relationship(
                user_handle=user_handle,
                first_met_at=datetime.now(),
                predefined_relationship=None,
                interaction_count=0,
                my_reply_count=0,
                their_reply_count=0,
                like_given_count=0,
                like_received_count=0,
                sentiment_history=[],
                sentiment_avg=0.0,
                common_topics=[],
                last_interaction_at=None
            )
            cursor.execute("""
                INSERT INTO relationships (user_handle, first_met_at, interaction_count)
                VALUES (?, ?, 0)
            """, (user_handle, datetime.now().isoformat()))
            return rel

    def update_relationship(self, rel: Relationship):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE relationships SET
                    interaction_count = ?, my_reply_count = ?, their_reply_count = ?,
                    like_given_count = ?, like_received_count = ?,
                    sentiment_history = ?, sentiment_avg = ?, common_topics = ?,
                    last_interaction_at = ?, updated_at = ?
                WHERE user_handle = ?
            """, (
                rel.interaction_count,
                rel.my_reply_count,
                rel.their_reply_count,
                rel.like_given_count,
                rel.like_received_count,
                json.dumps(rel.sentiment_history, ensure_ascii=False),
                rel.sentiment_avg,
                json.dumps(rel.common_topics, ensure_ascii=False),
                rel.last_interaction_at.isoformat() if rel.last_interaction_at else None,
                datetime.now().isoformat(),
                rel.user_handle
            ))

    def _row_to_relationship(self, row) -> Relationship:
        return Relationship(
            user_handle=row['user_handle'],
            first_met_at=datetime.fromisoformat(row['first_met_at']) if row['first_met_at'] else None,
            predefined_relationship=row['predefined_relationship'],
            interaction_count=row['interaction_count'],
            my_reply_count=row['my_reply_count'],
            their_reply_count=row['their_reply_count'],
            like_given_count=row['like_given_count'],
            like_received_count=row['like_received_count'],
            sentiment_history=json.loads(row['sentiment_history']) if row['sentiment_history'] else [],
            sentiment_avg=row['sentiment_avg'],
            common_topics=json.loads(row['common_topics']) if row['common_topics'] else [],
            last_interaction_at=datetime.fromisoformat(row['last_interaction_at']) if row['last_interaction_at'] else None
        )

    # ==================== Core Memory Methods ====================

    def add_core_memory(self, core: CoreMemory) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO core_memories (id, type, content, formed_from_inspiration_id, total_reinforcements, persona_impact, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                core.id,
                core.type,
                core.content,
                core.formed_from_inspiration_id,
                core.total_reinforcements,
                core.persona_impact,
                core.created_at.isoformat()
            ))
        return core.id

    def get_all_core_memories(self) -> List[CoreMemory]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM core_memories ORDER BY created_at DESC")
            return [self._row_to_core_memory(row) for row in cursor.fetchall()]

    def _row_to_core_memory(self, row) -> CoreMemory:
        return CoreMemory(
            id=row['id'],
            type=row['type'],
            content=row['content'],
            formed_from_inspiration_id=row['formed_from_inspiration_id'],
            total_reinforcements=row['total_reinforcements'],
            persona_impact=row['persona_impact'],
            created_at=datetime.fromisoformat(row['created_at'])
        )

    # ==================== Posting History Methods ====================

    def add_posting(self, inspiration_id: Optional[str], content: str, trigger_type: str, platform: str = 'twitter') -> str:
        post_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posting_history (id, platform, inspiration_id, content, trigger_type)
                VALUES (?, ?, ?, ?, ?)
            """, (post_id, platform, inspiration_id, content, trigger_type))
        return post_id

    def count_posts_today(self, platform: str = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM posting_history
                    WHERE date(posted_at) = date('now') AND platform = ?
                """, (platform,))
            else:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM posting_history
                    WHERE date(posted_at) = date('now')
                """)
            return cursor.fetchone()['count']

    def get_last_post_time(self) -> Optional[datetime]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT posted_at FROM posting_history ORDER BY posted_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            return datetime.fromisoformat(row['posted_at']) if row else None

    def get_recent_posts(self, limit: int = 5, platform: str = None) -> List[Dict]:
        """최근 게시글 조회 (플랫폼 필터 옵션)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute("""
                    SELECT content, trigger_type, posted_at, platform FROM posting_history
                    WHERE platform = ?
                    ORDER BY posted_at DESC LIMIT ?
                """, (platform, limit))
            else:
                cursor.execute("""
                    SELECT content, trigger_type, posted_at, platform FROM posting_history
                    ORDER BY posted_at DESC LIMIT ?
                """, (limit,))
            return [
                {"content": row['content'], "type": row['trigger_type'], "at": row['posted_at'], "platform": row['platform'] if 'platform' in row.keys() else 'twitter'}
                for row in cursor.fetchall()
            ]

    def get_recent_posts_context(self, limit: int = 5) -> str:
        """LLM 프롬프트용 최근 글 컨텍스트"""
        posts = self.get_recent_posts(limit)
        if not posts:
            return ""

        context = "### 📝 MY RECENT POSTS (avoid repeating similar content):\n"
        for p in posts:
            content_preview = p['content'][:80] + "..." if len(p['content']) > 80 else p['content']
            context += f"- {content_preview}\n"
        return context

    # ==================== Person Memory Methods (Social v2) ====================

    def get_or_create_person(self, user_id: str, screen_name: str, platform: str = 'twitter') -> PersonMemory:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM person_memories WHERE platform = ? AND user_id = ?",
                (platform, user_id)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_person_memory(row)

            now = datetime.now()
            person = PersonMemory(
                user_id=user_id,
                platform=platform,
                screen_name=screen_name,
                who_is_this="",
                tier='stranger',
                affinity=0.0,
                memorable_moments=[],
                latest_conversations=[],
                first_met_at=now,
                last_interaction_at=None,
                updated_at=now
            )
            cursor.execute("""
                INSERT INTO person_memories
                (user_id, platform, screen_name, tier, affinity, first_met_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, platform, screen_name, 'stranger', 0.0, now.isoformat(), now.isoformat()))
            return person

    def get_person(self, user_id: str, platform: str = 'twitter') -> Optional[PersonMemory]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM person_memories WHERE platform = ? AND user_id = ?",
                (platform, user_id)
            )
            row = cursor.fetchone()
            return self._row_to_person_memory(row) if row else None

    def get_persons_by_tier(self, tier: str, platform: str = 'twitter', limit: int = 50) -> List[PersonMemory]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM person_memories
                WHERE platform = ? AND tier = ?
                ORDER BY affinity DESC, last_interaction_at DESC
                LIMIT ?
            """, (platform, tier, limit))
            return [self._row_to_person_memory(row) for row in cursor.fetchall()]

    def get_familiar_persons(self, platform: str = 'twitter', limit: int = 50) -> List[PersonMemory]:
        """familiar 이상 티어의 사람들 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM person_memories
                WHERE platform = ? AND tier IN ('familiar', 'friend')
                ORDER BY affinity DESC
                LIMIT ?
            """, (platform, limit))
            return [self._row_to_person_memory(row) for row in cursor.fetchall()]

    def update_person(self, person: PersonMemory):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE person_memories SET
                    screen_name = ?,
                    who_is_this = ?,
                    tier = ?,
                    affinity = ?,
                    memorable_moments = ?,
                    latest_conversations = ?,
                    last_interaction_at = ?,
                    updated_at = ?
                WHERE platform = ? AND user_id = ?
            """, (
                person.screen_name,
                person.who_is_this,
                person.tier,
                person.affinity,
                json.dumps(person.memorable_moments, ensure_ascii=False),
                json.dumps(person.latest_conversations, ensure_ascii=False),
                person.last_interaction_at.isoformat() if person.last_interaction_at else None,
                datetime.now().isoformat(),
                person.platform,
                person.user_id
            ))

    def _row_to_person_memory(self, row) -> PersonMemory:
        return PersonMemory(
            user_id=row['user_id'],
            platform=row['platform'],
            screen_name=row['screen_name'],
            who_is_this=row['who_is_this'] or "",
            tier=row['tier'],
            affinity=row['affinity'],
            memorable_moments=json.loads(row['memorable_moments']) if row['memorable_moments'] else [],
            latest_conversations=json.loads(row['latest_conversations']) if row['latest_conversations'] else [],
            first_met_at=datetime.fromisoformat(row['first_met_at']) if row['first_met_at'] else datetime.now(),
            last_interaction_at=datetime.fromisoformat(row['last_interaction_at']) if row['last_interaction_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now()
        )

    # ==================== Conversation Record Methods (Social v2) ====================

    def add_conversation(self, conv: ConversationRecord) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_records
                (id, person_id, platform, post_id, conversation_type, topic, summary, turn_count, state, started_at, last_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conv.id,
                conv.person_id,
                conv.platform,
                conv.post_id,
                conv.conversation_type,
                conv.topic,
                conv.summary,
                conv.turn_count,
                conv.state,
                conv.started_at.isoformat(),
                conv.last_updated_at.isoformat()
            ))
        return conv.id

    def get_conversation(self, conv_id: str) -> Optional[ConversationRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversation_records WHERE id = ?", (conv_id,))
            row = cursor.fetchone()
            return self._row_to_conversation(row) if row else None

    def get_conversations_by_person(
        self, person_id: str, platform: str = 'twitter', limit: int = 10
    ) -> List[ConversationRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversation_records
                WHERE person_id = ? AND platform = ?
                ORDER BY last_updated_at DESC
                LIMIT ?
            """, (person_id, platform, limit))
            return [self._row_to_conversation(row) for row in cursor.fetchall()]

    def get_ongoing_conversations(self, platform: str = 'twitter', limit: int = 20) -> List[ConversationRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversation_records
                WHERE platform = ? AND state = 'ongoing'
                ORDER BY last_updated_at DESC
                LIMIT ?
            """, (platform, limit))
            return [self._row_to_conversation(row) for row in cursor.fetchall()]

    def update_conversation(self, conv: ConversationRecord):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversation_records SET
                    topic = ?,
                    summary = ?,
                    turn_count = ?,
                    state = ?,
                    last_updated_at = ?
                WHERE id = ?
            """, (
                conv.topic,
                conv.summary,
                conv.turn_count,
                conv.state,
                datetime.now().isoformat(),
                conv.id
            ))

    def _row_to_conversation(self, row) -> ConversationRecord:
        return ConversationRecord(
            id=row['id'],
            person_id=row['person_id'],
            platform=row['platform'],
            post_id=row['post_id'],
            conversation_type=row['conversation_type'],
            topic=row['topic'],
            summary=row['summary'] or "",
            turn_count=row['turn_count'],
            state=row['state'],
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else datetime.now(),
            last_updated_at=datetime.fromisoformat(row['last_updated_at']) if row['last_updated_at'] else datetime.now()
        )

    # ==================== Post Memory Methods ====================

    def get_post(self, post_id: str, platform: str = 'twitter') -> Optional[PostMemory]:
        """포스트 기억 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM post_memories WHERE platform = ? AND post_id = ?",
                (platform, post_id)
            )
            row = cursor.fetchone()
            return self._row_to_post_memory(row) if row else None

    def get_or_create_post(
        self,
        post_id: str,
        author_id: str,
        author_screen_name: str,
        content_preview: str,
        platform: str = 'twitter'
    ) -> PostMemory:
        """포스트 기억 조회 또는 생성"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM post_memories WHERE platform = ? AND post_id = ?",
                (platform, post_id)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_post_memory(row)

            now = datetime.now()
            preview = content_preview[:100] if len(content_preview) > 100 else content_preview
            post = PostMemory(
                post_id=post_id,
                platform=platform,
                author_id=author_id,
                author_screen_name=author_screen_name,
                content_preview=preview,
                my_reactions=[],
                my_reply_id=None,
                conversation_id=None,
                first_seen_at=now,
                last_interacted_at=None
            )
            cursor.execute("""
                INSERT INTO post_memories
                (post_id, platform, author_id, author_screen_name, content_preview, my_reactions, first_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                post_id, platform, author_id, author_screen_name,
                preview, json.dumps([]), now.isoformat()
            ))
            return post

    def has_reacted_to_post(self, post_id: str, reaction: str, platform: str = 'twitter') -> bool:
        """특정 반응을 이미 했는지 확인"""
        post = self.get_post(post_id, platform)
        if not post:
            return False
        return reaction in post.my_reactions

    def add_post_reaction(
        self,
        post_id: str,
        reaction: str,
        platform: str = 'twitter',
        reply_id: Optional[str] = None
    ) -> bool:
        """포스트에 반응 추가. 이미 있으면 False 반환."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT my_reactions, my_reply_id FROM post_memories WHERE platform = ? AND post_id = ?",
                (platform, post_id)
            )
            row = cursor.fetchone()

            if not row:
                return False

            reactions = json.loads(row['my_reactions']) if row['my_reactions'] else []
            if reaction in reactions:
                return False

            reactions.append(reaction)
            now = datetime.now().isoformat()

            if reaction == 'reply' and reply_id:
                cursor.execute("""
                    UPDATE post_memories SET
                        my_reactions = ?, my_reply_id = ?, last_interacted_at = ?
                    WHERE platform = ? AND post_id = ?
                """, (json.dumps(reactions), reply_id, now, platform, post_id))
            else:
                cursor.execute("""
                    UPDATE post_memories SET
                        my_reactions = ?, last_interacted_at = ?
                    WHERE platform = ? AND post_id = ?
                """, (json.dumps(reactions), now, platform, post_id))

            return True

    def link_post_to_conversation(self, post_id: str, conversation_id: str, platform: str = 'twitter'):
        """포스트를 대화에 연결"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE post_memories SET conversation_id = ?
                WHERE platform = ? AND post_id = ?
            """, (conversation_id, platform, post_id))

    def get_posts_by_author(
        self, author_id: str, platform: str = 'twitter', limit: int = 20
    ) -> List[PostMemory]:
        """특정 사용자의 포스트 기억 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM post_memories
                WHERE platform = ? AND author_id = ?
                ORDER BY first_seen_at DESC
                LIMIT ?
            """, (platform, author_id, limit))
            return [self._row_to_post_memory(row) for row in cursor.fetchall()]

    def get_reacted_posts(
        self, reaction: str, platform: str = 'twitter', limit: int = 50
    ) -> List[PostMemory]:
        """특정 반응을 한 포스트들 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM post_memories
                WHERE platform = ? AND my_reactions LIKE ?
                ORDER BY last_interacted_at DESC
                LIMIT ?
            """, (platform, f'%"{reaction}"%', limit))
            return [self._row_to_post_memory(row) for row in cursor.fetchall()]

    def _row_to_post_memory(self, row) -> PostMemory:
        return PostMemory(
            post_id=row['post_id'],
            platform=row['platform'],
            author_id=row['author_id'],
            author_screen_name=row['author_screen_name'],
            content_preview=row['content_preview'] or "",
            my_reactions=json.loads(row['my_reactions']) if row['my_reactions'] else [],
            my_reply_id=row['my_reply_id'],
            conversation_id=row['conversation_id'],
            first_seen_at=datetime.fromisoformat(row['first_seen_at']) if row['first_seen_at'] else datetime.now(),
            last_interacted_at=datetime.fromisoformat(row['last_interacted_at']) if row['last_interacted_at'] else None
        )


def generate_id() -> str:
    return str(uuid.uuid4())


# Global instance removed
# memory_db = MemoryDatabase()
