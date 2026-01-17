from agent.memory.database import MemoryDatabase
from agent.memory.inspiration_pool import InspirationPool
from agent.memory.tier_manager import TierManager
from agent.memory.consolidator import MemoryConsolidator
from agent.json_memory import agent_memory, AgentMemory

try:
    from agent.memory.vector_store import VectorStore
except ImportError:
    VectorStore = None

__all__ = [
    'MemoryDatabase',
    'VectorStore',
    'InspirationPool',
    'TierManager',
    'MemoryConsolidator',
    'agent_memory',
    'AgentMemory'
]
