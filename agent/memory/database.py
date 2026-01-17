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


class MemoryDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.MEMORY_DB_PATH
        self._ensure_data_dir()
        self._init_db()

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
                    user_handle TEXT PRIMARY KEY,
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
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspirations_tier ON inspirations(tier)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspirations_strength ON inspirations(strength)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_last_interaction ON relationships(last_interaction_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_usage_type ON pattern_usage(pattern_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_usage_at ON pattern_usage(used_at)")

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

    def add_posting(self, inspiration_id: Optional[str], content: str, trigger_type: str) -> str:
        post_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posting_history (id, inspiration_id, content, trigger_type)
                VALUES (?, ?, ?, ?)
            """, (post_id, inspiration_id, content, trigger_type))
        return post_id

    def count_posts_today(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
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

    def get_recent_posts(self, limit: int = 5) -> List[Dict]:
        """최근 게시글 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT content, trigger_type, posted_at FROM posting_history
                ORDER BY posted_at DESC LIMIT ?
            """, (limit,))
            return [
                {"content": row['content'], "type": row['trigger_type'], "at": row['posted_at']}
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


def generate_id() -> str:
    return str(uuid.uuid4())


# Global instance
memory_db = MemoryDatabase()
