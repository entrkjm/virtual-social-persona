import sys
import os
import unittest
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from agent.bot import SocialAgent
from agent.memory.factory import MemoryFactory
from config.settings import settings

class TestMemoryDI(unittest.TestCase):
    def setUp(self):
        print("\n[TestMemoryDI] Setting up...")
        # Ensure we are testing with 'chef_choi' as per migration
        self.persona_id = "chef_choi"
        
    def test_social_agent_initialization(self):
        print("[TestMemoryDI] Initializing SocialAgent (this should trigger MemoryFactory)...")
        agent = SocialAgent()
        
        # 1. Verify Agent has memory instances
        self.assertIsNotNone(agent.memory_db, "Agent should have memory_db")
        self.assertIsNotNone(agent.vector_store, "Agent should have vector_store")
        
        print(f"[TestMemoryDI] Agent DB Path: {agent.memory_db.db_path}")
        print(f"[TestMemoryDI] Agent Vector Path: {agent.vector_store.persist_directory}")
        
        # 2. Verify Paths match the new persona structure
        expected_db_path = os.path.join(settings.DATA_DIR, "personas", self.persona_id, "db", "memory.db")
        # Note: VectorStore appends 'chroma' internally or we pass it? 
        # Let's check what MemoryFactory does.
        # MemoryFactory: chroma_path = os.path.join(settings.DATA_DIR, "personas", persona_id, "db", "chroma")
        expected_chroma_path = os.path.join(settings.DATA_DIR, "personas", self.persona_id, "db", "chroma")
        
        self.assertEqual(os.path.abspath(agent.memory_db.db_path), os.path.abspath(expected_db_path))
        self.assertEqual(os.path.abspath(agent.vector_store.persist_directory), os.path.abspath(expected_chroma_path))
        
        # 3. Verify Sub-components share the SAME instance
        print("[TestMemoryDI] Verifying dependency injection into sub-components...")
        self.assertIs(agent.inspiration_pool.db, agent.memory_db)
        self.assertIs(agent.inspiration_pool.vector_store, agent.vector_store)
        
        self.assertIs(agent.memory_consolidator.db, agent.memory_db)
        self.assertIs(agent.memory_consolidator.vector_store, agent.vector_store)
        
        self.assertIs(agent.posting_trigger.db, agent.memory_db)
        self.assertIs(agent.posting_trigger.inspiration_pool, agent.inspiration_pool)
        
        self.assertIs(agent.pattern_tracker.db, agent.memory_db)
        
        print("[TestMemoryDI] All sub-components share the correct memory instances.")
        
    def test_db_access(self):
        print("[TestMemoryDI] Testing DB access...")
        # Use Factory directly to get DB
        db = MemoryFactory.get_memory_db(self.persona_id)
        
        # Simple read operation
        try:
            inspirations = db.get_all_inspirations()
            print(f"[TestMemoryDI] Successfully read {len(inspirations)} inspirations from DB.")
        except Exception as e:
            self.fail(f"DB read failed: {e}")

if __name__ == '__main__':
    unittest.main()
