"""
Memory Factory
페르소나별 메모리 인스턴스 생성 및 관리 (Singleton per Persona)
"""
import os
from typing import Dict
from config.settings import settings
from .database import MemoryDatabase
from .vector_store import VectorStore

class MemoryFactory:
    _dbs: Dict[str, MemoryDatabase] = {}
    _vectors: Dict[str, VectorStore] = {}

    @classmethod
    def get_memory_db(cls, persona_id: str) -> MemoryDatabase:
        if persona_id not in cls._dbs:
            # Path: data/personas/{id}/db/memory.db
            db_path = os.path.join(settings.DATA_DIR, "personas", persona_id, "db", "memory.db")
            cls._dbs[persona_id] = MemoryDatabase(db_path)
            print(f"[MemoryFactory] Loaded DB for {persona_id}: {db_path}")
        return cls._dbs[persona_id]

    @classmethod
    def get_vector_store(cls, persona_id: str) -> VectorStore:
        if persona_id not in cls._vectors:
            # Path: data/personas/{id}/db/chroma
            chroma_path = os.path.join(settings.DATA_DIR, "personas", persona_id, "db", "chroma")
            cls._vectors[persona_id] = VectorStore(persist_directory=chroma_path)
            print(f"[MemoryFactory] Loaded VectorStore for {persona_id}: {chroma_path}")
        return cls._vectors[persona_id]

    @classmethod
    def reset(cls):
        """테스트용 리셋"""
        cls._dbs.clear()
        cls._vectors.clear()
