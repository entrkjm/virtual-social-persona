"""
Vector Store
Chroma + Gemini Embedding 시맨틱 검색
Semantic search with Chroma and Gemini embeddings
"""
import os
import chromadb
from chromadb.config import Settings as ChromaSettings
from google import genai
from typing import List, Dict, Optional, Any
from config.settings import settings


class GeminiEmbeddingFunction:
    """Gemini Embedding API를 사용하는 임베딩 함수
    chromadb 1.4+ 호환, google.genai SDK
    """

    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = "gemini-embedding-exp-03-07"
        self._name = "gemini-embedding"

    def name(self) -> str:
        """chromadb 1.4+ 필수 메서드"""
        return self._name

    def __call__(self, input: List[str]) -> List[List[float]]:
        """Chroma - documents 임베딩"""
        return self.embed_documents(input)

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """문서 리스트 임베딩"""
        if not self.client:
            return [[0.0] * 3072 for _ in documents]

        embeddings = []
        for text in documents:
            try:
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=text
                )
                embeddings.append(list(result.embeddings[0].values))
            except Exception as e:
                print(f"[EMBEDDING ERROR] {e}")
                embeddings.append([0.0] * 3072)
        return embeddings

    def embed_query(self, input: str) -> List[float]:
        """단일 쿼리 임베딩 (chromadb 검색용)"""
        if not self.client:
            return [0.0] * 3072

        try:
            result = self.client.models.embed_content(
                model=self.model,
                contents=input
            )
            return list(result.embeddings[0].values)
        except Exception as e:
            print(f"[EMBEDDING ERROR] {e}")
            return [0.0] * 3072


class VectorStore:
    """Chroma 기반 벡터 저장소"""

    def __init__(self, persist_directory: str = None):
        self.persist_directory = persist_directory or settings.CHROMA_PATH
        self._ensure_data_dir()
        self.embedding_fn = GeminiEmbeddingFunction()

        # Chroma 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # 컬렉션 초기화
        self._init_collections()

    def _with_timeout(self, func, *args, timeout_seconds=5, **kwargs):
        """실행 시간 제한 래퍼"""
        import concurrent.futures
        
        # Don't use 'with' - it waits for shutdown
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(func, *args, **kwargs)
            try:
                # print(f"Wait for {timeout_seconds}s...")
                return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                print(f"[VECTOR] Operation timed out ({timeout_seconds}s)", flush=True)
                return None
            except Exception as e:
                print(f"[VECTOR] Operation failed: {e}")
                return None
        finally:
            # wait=False means don't wait for pending futures to complete
            executor.shutdown(wait=False, cancel_futures=False)

    def _ensure_data_dir(self):
        """데이터 디렉토리 생성 / Ensure data directory exists"""
        os.makedirs(self.persist_directory, exist_ok=True)

    def _init_collections(self):
        """컬렉션 생성/로드"""
        # Episodes 컬렉션 (경험)
        self.episodes = self.client.get_or_create_collection(
            name="episodes",
            embedding_function=self.embedding_fn,
            metadata={"description": "에피소드 기억 - 모든 경험의 임베딩"}
        )

        # Inspirations 컬렉션 (영감)
        self.inspirations = self.client.get_or_create_collection(
            name="inspirations",
            embedding_function=self.embedding_fn,
            metadata={"description": "영감 저장소 - 글감 아이디어"}
        )

    # ==================== Episode Methods ====================

    def add_episode(self, id: str, content: str, metadata: Dict[str, Any]):
        """에피소드 임베딩 추가"""
        try:
            self.episodes.add(
                ids=[id],
                documents=[content],
                metadatas=[self._sanitize_metadata(metadata)]
            )
        except Exception as e:
            print(f"[VECTOR] Failed to add episode: {e}")

    def search_similar_episodes(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> List[Dict]:
        """유사한 에피소드 검색"""
        try:
            query_embedding = self.embedding_fn.embed_query(input=query)
            results = self.episodes.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return self._format_results(results)
        except Exception as e:
            print(f"[VECTOR] Search failed: {e}")
            return []

    # ==================== Inspiration Methods ====================

    def add_inspiration(self, id: str, content: str, metadata: Dict[str, Any]):
        """영감 임베딩 추가

        Args:
            id: 영감 ID
            content: 검색용 텍스트 (trigger_content + my_angle 조합 권장)
            metadata: 메타데이터 (tier, strength, topic 등)
        """
        try:
            self.inspirations.add(
                ids=[id],
                documents=[content],
                metadatas=[self._sanitize_metadata(metadata)]
            )
        except Exception as e:
            print(f"[VECTOR] Failed to add inspiration: {e}")

    def update_inspiration_metadata(self, id: str, metadata: Dict[str, Any]):
        """영감 메타데이터 업데이트 (tier, strength 등)"""
        try:
            self.inspirations.update(
                ids=[id],
                metadatas=[self._sanitize_metadata(metadata)]
            )
        except Exception as e:
            print(f"[VECTOR] Failed to update inspiration: {e}")

    def update_inspirations_batch(self, ids: List[str], metadatas: List[Dict[str, Any]]):
        """영감 메타데이터 일괄 업데이트 (Batch Update)"""
        if not ids:
            return
        
        try:
            # Sanitize all metadata
            sanitized_metadatas = [self._sanitize_metadata(m) for m in metadatas]
            
            # Wrap update call
            def _do_update():
                self.inspirations.update(
                    ids=ids,
                    metadatas=sanitized_metadatas
                )
            
            self._with_timeout(_do_update, timeout_seconds=5)
            # print(f"[VECTOR] Batch updated {len(ids)} inspirations")
        except Exception as e:
            print(f"[VECTOR] Failed to batch update inspirations: {e}")

    def delete_inspiration(self, id: str):
        """영감 삭제"""
        try:
            # Wrap delete call
            def _do_delete():
                self.inspirations.delete(ids=[id])
            self._with_timeout(_do_delete, timeout_seconds=5)
        except Exception as e:
            print(f"[VECTOR] Failed to delete inspiration: {e}")

    def delete_inspirations_batch(self, ids: List[str]):
        """영감 일괄 삭제 (Batch Delete)"""
        if not ids:
            return
            
        try:
            # Wrap batch delete
            def _do_batch_delete():
                self.inspirations.delete(ids=ids)
            
            self._with_timeout(_do_batch_delete, timeout_seconds=5)
            print(f"[VECTOR] Batch deleted {len(ids)} inspirations")
        except Exception as e:
            print(f"[VECTOR] Failed to batch delete inspirations: {e}")

    def search_similar_inspirations(
        self,
        query: str,
        n_results: int = 5,
        min_strength: Optional[float] = None,
        tiers: Optional[List[str]] = None
    ) -> List[Dict]:
        """유사한 영감 검색

        Args:
            query: 검색 쿼리
            n_results: 반환할 결과 수
            min_strength: 최소 강도 필터
            tiers: 티어 필터 (예: ['short_term', 'long_term'])

        Returns:
            [{"id": "...", "content": "...", "distance": 0.3, "metadata": {...}}, ...]
        """
        try:
            where = {}

            if min_strength is not None:
                where["strength"] = {"$gte": min_strength}

            if tiers:
                where["tier"] = {"$in": tiers}

            query_embedding = self.embedding_fn.embed_query(input=query)
            results = self.inspirations.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where if where else None
            )
            return self._format_results(results)
        except Exception as e:
            print(f"[VECTOR] Search failed: {e}")
            return []

    def find_reinforcement_candidates(
        self,
        content: str,
        similarity_threshold: float = 0.3,
        n_results: int = 10
    ) -> List[Dict]:
        """강화 후보 찾기 - 유사도 높은 영감들

        Args:
            content: 새로 본 콘텐츠
            similarity_threshold: 최소 유사도 (거리 기준, 낮을수록 유사)
            n_results: 검색할 최대 개수

        Returns:
            유사도가 threshold 이하인 영감들
        """
        results = self.search_similar_inspirations(query=content, n_results=n_results)

        # 유사도 필터링 (Chroma는 L2 거리 사용, 낮을수록 유사)
        return [r for r in results if r['distance'] <= similarity_threshold]

    # ==================== Utility Methods ====================

    def _format_results(self, results: Dict) -> List[Dict]:
        """Chroma 결과를 표준 형식으로 변환"""
        formatted = []

        if not results or not results.get('ids') or not results['ids'][0]:
            return []

        for i, id in enumerate(results['ids'][0]):
            formatted.append({
                'id': id,
                'content': results['documents'][0][i] if results.get('documents') else None,
                'distance': results['distances'][0][i] if results.get('distances') else None,
                'metadata': results['metadatas'][0][i] if results.get('metadatas') else {}
            })

        return formatted

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Chroma 호환 메타데이터로 변환 (문자열, 숫자, 불리언만 허용)"""
        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list):
                # 리스트는 문자열로 변환
                sanitized[key] = ",".join(str(v) for v in value)
            else:
                sanitized[key] = str(value)
        return sanitized

    def get_stats(self) -> Dict[str, int]:
        """저장소 통계"""
        return {
            'episodes_count': self.episodes.count(),
            'inspirations_count': self.inspirations.count()
        }


# Global instance removed
# vector_store = VectorStore()
