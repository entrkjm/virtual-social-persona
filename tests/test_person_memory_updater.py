"""
Test PersonMemoryUpdater
Mock 데이터로 LLM 기반 who_is_this 업데이트 테스트
"""
import sys
import os
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.append(os.getcwd())

from agent.memory.database import PersonMemory
from agent.memory.person_memory_updater import PersonMemoryUpdater


class TestPersonMemoryUpdater(unittest.TestCase):
    def setUp(self):
        self.updater = PersonMemoryUpdater(db=None)

    def _create_mock_person(
        self,
        screen_name: str = "test_user",
        tier: str = "acquaintance",
        affinity: float = 0.3,
        conversations: int = 0,
        moments: int = 0
    ) -> PersonMemory:
        """테스트용 PersonMemory 생성"""
        latest_conversations = []
        for i in range(conversations):
            latest_conversations.append({
                "id": f"conv_{i}",
                "date": "2024-01-15",
                "type": "reply",
                "topic": ["요리", "일상", "기술"][i % 3],
                "summary": f"대화 요약 #{i + 1}"
            })

        memorable_moments = []
        for i in range(moments):
            memorable_moments.append({
                "date": "2024-01-10",
                "summary": f"인상적인 순간 #{i + 1}"
            })

        return PersonMemory(
            user_id=f"user_{screen_name}",
            platform="twitter",
            screen_name=screen_name,
            who_is_this="",
            tier=tier,
            affinity=affinity,
            memorable_moments=memorable_moments,
            latest_conversations=latest_conversations,
            first_met_at=datetime.now(),
            last_interaction_at=datetime.now(),
            updated_at=datetime.now()
        )

    def test_should_update_returns_false_for_insufficient_data(self):
        """데이터 부족 시 업데이트 불필요"""
        person = self._create_mock_person(conversations=1, moments=0)
        self.assertFalse(self.updater.should_update(person))

    def test_should_update_returns_true_for_sufficient_conversations(self):
        """대화 3회 이상이면 업데이트 필요"""
        person = self._create_mock_person(conversations=3, moments=0)
        self.assertTrue(self.updater.should_update(person))

    def test_should_update_returns_true_for_memorable_moment(self):
        """인상적인 순간 1회 이상이면 업데이트 필요"""
        person = self._create_mock_person(conversations=0, moments=1)
        self.assertTrue(self.updater.should_update(person))

    def test_build_prompt_includes_screen_name(self):
        """프롬프트에 screen_name 포함"""
        person = self._create_mock_person(
            screen_name="chef_fan",
            conversations=3
        )
        prompt = self.updater._build_prompt(person)
        self.assertIn("@chef_fan", prompt)

    def test_build_prompt_includes_tier_and_affinity(self):
        """프롬프트에 관계 정보 포함"""
        person = self._create_mock_person(
            tier="familiar",
            affinity=0.7,
            conversations=3
        )
        prompt = self.updater._build_prompt(person)
        self.assertIn("familiar", prompt)
        self.assertIn("0.70", prompt)

    def test_build_prompt_includes_conversations(self):
        """프롬프트에 대화 내역 포함"""
        person = self._create_mock_person(conversations=3)
        prompt = self.updater._build_prompt(person)
        self.assertIn("최근 대화:", prompt)
        self.assertIn("대화 요약 #1", prompt)

    def test_build_prompt_includes_moments(self):
        """프롬프트에 기억에 남는 순간 포함"""
        person = self._create_mock_person(moments=2, conversations=3)
        prompt = self.updater._build_prompt(person)
        self.assertIn("기억에 남는 순간:", prompt)
        self.assertIn("인상적인 순간 #1", prompt)

    def test_clean_response_removes_quotes(self):
        """응답에서 따옴표 제거"""
        result = self.updater._clean_response('"요리에 관심 많은 개발자"')
        self.assertEqual(result, "요리에 관심 많은 개발자")

    def test_clean_response_truncates_long_text(self):
        """100자 초과 시 잘라냄"""
        long_text = "a" * 150
        result = self.updater._clean_response(long_text)
        self.assertEqual(len(result), 100)

    @patch('agent.memory.person_memory_updater.llm_client')
    def test_update_who_is_this_success(self, mock_llm):
        """LLM 호출 성공 시 who_is_this 업데이트"""
        mock_llm.generate.return_value = "요리에 관심 많은 개발자"

        person = self._create_mock_person(conversations=5)
        result = self.updater.update_who_is_this(person)

        self.assertEqual(result, "요리에 관심 많은 개발자")
        self.assertEqual(person.who_is_this, "요리에 관심 많은 개발자")
        mock_llm.generate.assert_called_once()

    @patch('agent.memory.person_memory_updater.llm_client')
    def test_update_who_is_this_skips_insufficient_data(self, mock_llm):
        """데이터 부족 시 업데이트 건너뜀"""
        person = self._create_mock_person(conversations=1)
        result = self.updater.update_who_is_this(person)

        self.assertIsNone(result)
        mock_llm.generate.assert_not_called()

    @patch('agent.memory.person_memory_updater.llm_client')
    def test_update_who_is_this_handles_llm_error(self, mock_llm):
        """LLM 에러 처리"""
        mock_llm.generate.side_effect = Exception("LLM unavailable")

        person = self._create_mock_person(conversations=5)
        result = self.updater.update_who_is_this(person)

        self.assertIsNone(result)

    @patch('agent.memory.person_memory_updater.llm_client')
    def test_batch_update(self, mock_llm):
        """일괄 업데이트 통계 확인"""
        mock_llm.generate.return_value = "테스트 요약"

        persons = [
            self._create_mock_person(screen_name="user1", conversations=5),
            self._create_mock_person(screen_name="user2", conversations=1),
            self._create_mock_person(screen_name="user3", conversations=4),
        ]

        stats = self.updater.batch_update(persons)

        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['updated'], 2)
        self.assertEqual(stats['skipped'], 1)

    @patch('agent.memory.person_memory_updater.llm_client')
    def test_batch_update_force(self, mock_llm):
        """강제 업데이트 모드"""
        mock_llm.generate.return_value = "강제 요약"

        persons = [
            self._create_mock_person(screen_name="user1", conversations=1),
        ]

        stats = self.updater.batch_update(persons, force=True)

        self.assertEqual(stats['updated'], 1)
        self.assertEqual(stats['skipped'], 0)


class TestPersonMemoryUpdaterWithDB(unittest.TestCase):
    """DB 연동 테스트 (실제 DB 사용)"""

    @patch('agent.memory.person_memory_updater.llm_client')
    def test_update_with_db_save(self, mock_llm):
        """DB 저장 확인"""
        mock_db = MagicMock()
        updater = PersonMemoryUpdater(db=mock_db)

        mock_llm.generate.return_value = "DB 저장 테스트"

        person = PersonMemory(
            user_id="db_test_user",
            platform="twitter",
            screen_name="db_tester",
            who_is_this="",
            tier="acquaintance",
            affinity=0.5,
            memorable_moments=[],
            latest_conversations=[
                {"topic": "test1", "summary": "대화1"},
                {"topic": "test2", "summary": "대화2"},
                {"topic": "test3", "summary": "대화3"},
            ],
            first_met_at=datetime.now(),
            last_interaction_at=datetime.now(),
            updated_at=datetime.now()
        )

        result = updater.update_who_is_this(person)

        self.assertEqual(result, "DB 저장 테스트")
        mock_db.update_person.assert_called_once_with(person)


if __name__ == '__main__':
    unittest.main()
