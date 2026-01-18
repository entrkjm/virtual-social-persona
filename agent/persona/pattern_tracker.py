"""
Pattern Tracker
말투 패턴 사용 추적 / 위반 감지
Usage tracking and violation detection for speech patterns
"""
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from config.settings import settings
# from agent.memory.database import memory_db


@dataclass
class PatternViolation:
    pattern_type: str  # 'signature', 'frequent', 'filler'
    pattern: str
    violation_reason: str
    current_count: int
    max_allowed: int


@dataclass
class PatternRegistry:
    """페르소나에서 로드된 패턴 설정"""
    signature: Dict  # cooldown_posts 기반
    frequent: Dict   # max_consecutive 기반
    filler: Dict     # max_per_post 기반
    contextual: Dict # 맥락별 설정
    persona_traits: Dict  # 페르소나 특성 설명


class PatternTracker:
    def __init__(self, db, pattern_registry: Optional[Dict] = None):
        self.db = db
        self.registry = self._parse_registry(pattern_registry or {})

    def _parse_registry(self, config: Dict) -> PatternRegistry:
        return PatternRegistry(
            signature=config.get('signature', {
                'patterns': [],
                'cooldown_posts': 5,
                'is_core_trait': False
            }),
            frequent=config.get('frequent', {
                'patterns': [],
                'max_consecutive': 2,
                'min_consecutive': 0,
                'is_core_trait': False
            }),
            filler=config.get('filler', {
                'patterns': [],
                'max_per_post': 2,
                'min_per_post': 0,
                'is_core_trait': False
            }),
            contextual=config.get('contextual', {}),
            persona_traits=config.get('persona_traits', {
                'description': '',
                'core_characteristics': []
            })
        )

    def record_usage(self, text: str, post_id: Optional[str] = None) -> List[str]:
        """텍스트에서 패턴 추출 후 사용 기록. 기록된 패턴 반환"""
        if not post_id:
            post_id = str(uuid.uuid4())

        recorded = []

        for pattern_type, config in [
            ('signature', self.registry.signature),
            ('frequent', self.registry.frequent),
            ('filler', self.registry.filler)
        ]:
            for pattern in config.get('patterns', []):
                if self._pattern_in_text(pattern, text):
                    self._insert_usage(pattern_type, pattern, post_id)
                    recorded.append(f"{pattern_type}:{pattern}")

        return recorded

    def _pattern_in_text(self, pattern: str, text: str) -> bool:
        """패턴이 텍스트에 존재하는지 확인 (정규식 지원)"""
        try:
            escaped = re.escape(pattern).replace(r'\~', '~')
            return bool(re.search(escaped, text))
        except re.error:
            return pattern in text

    def _insert_usage(self, pattern_type: str, pattern: str, post_id: str):
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pattern_usage (pattern_type, pattern, post_id)
                VALUES (?, ?, ?)
            """, (pattern_type, pattern, post_id))

    def get_pattern_count(self, pattern_type: str, pattern: str, last_n_posts: int = 5) -> int:
        """최근 N개 포스트에서 특정 패턴 사용 횟수"""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            # 최근 N개 포스트 ID 조회
            cursor.execute("""
                SELECT DISTINCT post_id FROM pattern_usage
                ORDER BY used_at DESC
                LIMIT ?
            """, (last_n_posts,))
            recent_posts = [row['post_id'] for row in cursor.fetchall()]

            if not recent_posts:
                return 0

            placeholders = ','.join(['?' for _ in recent_posts])
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM pattern_usage
                WHERE pattern_type = ? AND pattern = ? AND post_id IN ({placeholders})
            """, [pattern_type, pattern] + recent_posts)

            return cursor.fetchone()['count']

    def get_consecutive_count(self, pattern_type: str, pattern: str) -> int:
        """연속 사용 횟수 (최근부터 연속으로 사용된 횟수)"""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT post_id FROM pattern_usage
                WHERE pattern_type = ?
                ORDER BY used_at DESC
                LIMIT 10
            """, (pattern_type,))

            count = 0
            for row in cursor.fetchall():
                # 해당 포스트에서 이 패턴 사용 여부
                cursor.execute("""
                    SELECT 1 FROM pattern_usage
                    WHERE post_id = ? AND pattern = ?
                """, (row['post_id'], pattern))

                if cursor.fetchone():
                    count += 1
                else:
                    break

            return count

    def get_last_signature_use(self, pattern: str) -> Tuple[Optional[datetime], int]:
        """시그니처 패턴 마지막 사용 시점과 그 이후 포스트 수"""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT used_at, post_id FROM pattern_usage
                WHERE pattern_type = 'signature' AND pattern = ?
                ORDER BY used_at DESC
                LIMIT 1
            """, (pattern,))

            row = cursor.fetchone()
            if not row:
                return None, 0

            last_used = datetime.fromisoformat(row['used_at'])

            # 그 이후 포스트 수
            cursor.execute("""
                SELECT COUNT(DISTINCT post_id) as count FROM pattern_usage
                WHERE used_at > ?
            """, (row['used_at'],))

            posts_since = cursor.fetchone()['count']
            return last_used, posts_since

    def check_violations(self, text: str, topic_context: Optional[str] = None) -> List[PatternViolation]:
        """생성된 텍스트의 패턴 위반 사항 체크"""
        violations = []

        # 1. 시그니처 쿨다운 체크
        cooldown = self.registry.signature.get('cooldown_posts', 5)
        for pattern in self.registry.signature.get('patterns', []):
            if self._pattern_in_text(pattern, text):
                _, posts_since = self.get_last_signature_use(pattern)
                if posts_since < cooldown and posts_since > 0:
                    violations.append(PatternViolation(
                        pattern_type='signature',
                        pattern=pattern,
                        violation_reason=f'쿨다운 미충족 (필요: {cooldown}개, 현재: {posts_since}개)',
                        current_count=posts_since,
                        max_allowed=cooldown
                    ))

        # 2. frequent 연속 사용 체크
        max_consecutive = self.registry.frequent.get('max_consecutive', 2)
        for pattern in self.registry.frequent.get('patterns', []):
            if self._pattern_in_text(pattern, text):
                consecutive = self.get_consecutive_count('frequent', pattern)
                if consecutive >= max_consecutive:
                    violations.append(PatternViolation(
                        pattern_type='frequent',
                        pattern=pattern,
                        violation_reason=f'연속 사용 초과 (최대: {max_consecutive}회, 현재: {consecutive+1}회)',
                        current_count=consecutive + 1,
                        max_allowed=max_consecutive
                    ))

        # 3. filler 글 내 과다 사용 체크
        max_per_post = self.registry.filler.get('max_per_post', 1)
        for pattern in self.registry.filler.get('patterns', []):
            count = len(re.findall(re.escape(pattern), text))
            if count > max_per_post:
                violations.append(PatternViolation(
                    pattern_type='filler',
                    pattern=pattern,
                    violation_reason=f'글 내 과다 사용 (최대: {max_per_post}회, 현재: {count}회)',
                    current_count=count,
                    max_allowed=max_per_post
                ))

        # 4. contextual 체크
        if topic_context:
            context_config = self.registry.contextual.get(topic_context, {})
            avoid_patterns = context_config.get('avoid', [])
            for pattern in avoid_patterns:
                if self._pattern_in_text(pattern, text):
                    violations.append(PatternViolation(
                        pattern_type='contextual',
                        pattern=pattern,
                        violation_reason=f'{topic_context} 맥락에서 사용 금지',
                        current_count=1,
                        max_allowed=0
                    ))

        return violations

    def format_violations_for_llm(self, violations: List[PatternViolation]) -> str:
        """LLM에게 전달할 위반 사항 포맷팅"""
        if not violations:
            return ""

        lines = ["### 패턴 위반 사항 (반드시 교정 필요):"]

        for v in violations:
            if v.pattern_type == 'signature':
                lines.append(f"- 시그니처 패턴 '{v.pattern}' 쿨다운 미충족. 다른 표현으로 교체하세요.")
            elif v.pattern_type == 'frequent':
                lines.append(f"- '{v.pattern}' 패턴이 연속 {v.current_count}회 사용됨. 다른 어미로 교체하세요.")
            elif v.pattern_type == 'filler':
                lines.append(f"- 채움말 '{v.pattern}'이 {v.current_count}회 사용됨 (최대 {v.max_allowed}회). 일부 제거하세요.")
            elif v.pattern_type == 'contextual':
                lines.append(f"- '{v.pattern}'은 현재 맥락에서 부적절함. 제거 또는 교체하세요.")

        return '\n'.join(lines)

    def get_preferred_alternatives(self, pattern_type: str, avoid_pattern: str) -> List[str]:
        """회피할 패턴 대신 사용 가능한 대안 패턴"""
        config = getattr(self.registry, pattern_type, {})
        patterns = config.get('patterns', [])
        return [p for p in patterns if p != avoid_pattern]

    def get_persona_preservation_prompt(self) -> str:
        """페르소나 보존을 위한 리뷰어 가이드 생성"""
        lines = []

        # 페르소나 설명
        traits = self.registry.persona_traits
        if traits.get('description'):
            lines.append(f"### 페르소나 특성:")
            lines.append(f"- {traits['description']}")

        if traits.get('core_characteristics'):
            lines.append("\n### 핵심 특성 (반드시 유지):")
            for char in traits['core_characteristics']:
                lines.append(f"- {char}")

        # 보존해야 할 패턴
        preserve_rules = []

        # filler 보존 규칙
        filler = self.registry.filler
        if filler.get('is_core_trait') and filler.get('min_per_post', 0) > 0:
            patterns_str = ', '.join(filler.get('patterns', [])[:3])
            reason = filler.get('preserve_reason', '페르소나 특성')
            preserve_rules.append(
                f"- 채움말({patterns_str})은 최소 {filler['min_per_post']}회 유지 "
                f"(이유: {reason})"
            )

        # signature 보존 규칙
        signature = self.registry.signature
        if signature.get('is_core_trait'):
            preserve_rules.append(
                f"- 시그니처 표현은 삭제하지 말고, 쿨다운만 준수"
            )

        if preserve_rules:
            lines.append("\n### 패턴 보존 규칙:")
            lines.extend(preserve_rules)

        # 교정 한도 설명
        limits = []
        filler_max = filler.get('max_per_post', 2)
        filler_min = filler.get('min_per_post', 0)
        if filler_max > 0:
            limits.append(f"- 채움말: {filler_min}~{filler_max}회 범위로 유지")

        frequent = self.registry.frequent
        freq_max = frequent.get('max_consecutive', 2)
        if freq_max > 0:
            limits.append(f"- 어미 패턴: 연속 {freq_max}회 이상만 교정")

        if limits:
            lines.append("\n### 교정 범위:")
            lines.extend(limits)
            lines.append("- 범위 내라면 교정하지 마세요")

        return '\n'.join(lines) if lines else ""


def create_pattern_tracker(persona_config) -> PatternTracker:
    """페르소나 설정에서 PatternTracker 생성"""
    registry = {}

    # PersonaConfig 객체인 경우 raw_data에서 가져옴
    if hasattr(persona_config, 'raw_data'):
        registry = persona_config.raw_data.get('pattern_registry', {})
    elif hasattr(persona_config, 'pattern_registry'):
        registry = persona_config.pattern_registry
    elif isinstance(persona_config, dict):
        registry = persona_config.get('pattern_registry', {})

    return PatternTracker(registry)
