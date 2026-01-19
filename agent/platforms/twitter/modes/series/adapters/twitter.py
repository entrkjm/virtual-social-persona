"""
Platform Adapter Base & Twitter Adapter
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import time
import random
from platforms.twitter.social import post_tweet

class PlatformAdapter(ABC):
    @abstractmethod
    def publish(self, content: str, images: List[str], config: Dict) -> Dict:
        """
        콘텐츠 게시
        Returns:
            Dict: {"id": "post_id", "url": "..."}
        """
        pass

class TwitterAdapter(PlatformAdapter):
    MAX_LENGTH = 200  # Reduced further for safety
    MAX_THREAD_LENGTH = 3  # 최대 3개 트윗으로 제한
    TWEET_DELAY_BASE = 20  # 기본 딜레이 20초
    TWEET_DELAY_RANDOM = 10  # 랜덤 추가 0~10초
    
    def _get_random_delay(self) -> int:
        """랜덤 딜레이 계산: 20 + random(0-10)"""
        return self.TWEET_DELAY_BASE + random.randint(0, self.TWEET_DELAY_RANDOM)
    
    def publish(self, content: str, images: List[str], config: Dict) -> Dict:
        format_type = config.get('format', 'single')
        
        # 1. 콘텐츠 분할 (스레드) - 최대 길이 제한 (split_content 내부에서 처리됨)
        chunks = self._split_content(content)
        
        # 안전장치: 빈 청크 필터링
        chunks = [c for c in chunks if c and c.strip()]
        
        if not chunks:
            print("[TwitterAdapter] No content to publish!")
            return {"id": None, "platform": "twitter"}
        
        print(f"[TwitterAdapter] Publishing {len(chunks)} tweets (images={len(images)})...")
        print(f"[TwitterAdapter] First chunk preview: {chunks[0][:50]}..." if chunks else "No chunks")
        
        # 2. 순차 게시
        first_tweet_id = None
        reply_to = None
        
        for i, chunk in enumerate(chunks):
            # 첫 트윗에만 이미지 첨부 (이미지 + 텍스트 함께)
            media = images if i == 0 else []
            
            print(f"[TwitterAdapter] Tweet {i+1}/{len(chunks)}: text={len(chunk)}chars, images={len(media)}")
            
            try:
                tweet_id = post_tweet(chunk, media_files=media, reply_to=reply_to)
                if i == 0:
                    first_tweet_id = tweet_id
                
                reply_to = tweet_id
                
                # 봇 감지 방지용 랜덤 딜레이 (마지막 트윗 제외)
                if i < len(chunks) - 1:
                    delay = self._get_random_delay()
                    print(f"[TwitterAdapter] Waiting {delay}s before next tweet...")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"[TwitterAdapter] Failed to publish tweet {i+1}/{len(chunks)}: {e}")
                # 중간에 실패하면 멈춤 (나중에 재시도 로직 추가 필요)
                break
                
        return {"id": first_tweet_id, "platform": "twitter"}

    def _split_content(self, content: str) -> List[str]:
        """
        콘텐츠를 HOOK + DETAIL 구조로 분할
        
        Expected format from LLM:
        ===HOOK===
        짧은 훅 텍스트 (이미지와 함께)
        ===DETAIL===
        상세 설명 (댓글로)
        """
        if not content or not content.strip():
            return []
        
        # HOOK/DETAIL 구분자로 파싱 시도
        hook_marker = "===HOOK==="
        detail_marker = "===DETAIL==="
        
        hook = ""
        detail = ""
        
        if hook_marker in content and detail_marker in content:
            # 구조화된 형식 파싱
            parts = content.split(detail_marker)
            hook_part = parts[0].replace(hook_marker, "").strip()
            detail_part = parts[1].strip() if len(parts) > 1 else ""
            
            hook = hook_part
            detail = detail_part
            
            print(f"[TwitterAdapter] Parsed structured content: HOOK={len(hook)}chars, DETAIL={len(detail)}chars")
    def _chunk_text_preserving_sentences(self, text: str, max_len: int) -> List[str]:
        """문장 단위를 보존하며 텍스트를 청크로 분할"""
        if not text:
            return []
            
        chunks = []
        current_chunk = ""
        
        # 1. 문단 단위 분할
        paragraphs = text.split('\n')
        
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
                
            # 문단이 한도보다 작으면 기존 청크에 추가 시도
            if len(current_chunk) + len(p) + 1 <= max_len:
                current_chunk += ("\n" + p if current_chunk else p)
            else:
                # 문단이 너무 길거나, 기존 청크와 합치면 넘치는 경우
                
                # 기존 청크가 있으면 먼저 저장
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # 문단 자체가 한도보다 작으면 새 청크로 시작
                if len(p) <= max_len:
                    current_chunk = p
                else:
                    # 문단 자체가 한도보다 크면 문장 단위로 쪼개기
                    # . ! ? 뒤에 공백이 있는 경우를 문장 끝으로 간주
                    # 정교한 분할을 위해 임시로 특수문자로 치환 후 분할할 수도 있지만
                    # 간단히 . ! ? 로 split 후 재조합
                    import re
                    sentences = re.split(r'(?<=[.!?])\s+', p)
                    
                    sub_chunk = ""
                    for s in sentences:
                        # 문장이 한도보다 작으면 합치기
                        if len(sub_chunk) + len(s) + 1 <= max_len:
                            sub_chunk += (" " + s if sub_chunk else s)
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                                sub_chunk = ""
                            
                            # 단일 문장이 한도보다 크면 강제 분할 (어쩔 수 없음)
                            if len(s) > max_len:
                                while s:
                                    chunks.append(s[:max_len])
                                    s = s[max_len:]
                            else:
                                sub_chunk = s
                    
                    if sub_chunk:
                        current_chunk = sub_chunk
                        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _split_content(self, content: str) -> List[str]:
        """
        콘텐츠를 HOOK + DETAIL 구조로 분할
        """
        if not content or not content.strip():
            return []
        
        # HOOK/DETAIL 구분자로 파싱 시도
        hook_marker = "===HOOK==="
        detail_marker = "===DETAIL==="
        
        hook = ""
        detail = ""
        
        if hook_marker in content and detail_marker in content:
            # 구조화된 형식 파싱
            parts = content.split(detail_marker)
            hook_part = parts[0].replace(hook_marker, "").strip()
            detail_part = parts[1].strip() if len(parts) > 1 else ""
            
            hook = hook_part
            detail = detail_part
            print(f"[TwitterAdapter] Parsed structured content: HOOK={len(hook)}chars, DETAIL={len(detail)}chars")
            
            result = []
            
            # HOOK 처리
            if hook:
                # HOOK은 단일 트윗으로, 너무 길면 문장 단위 분할
                hook_chunks = self._chunk_text_preserving_sentences(hook, self.MAX_LENGTH)
                result.extend(hook_chunks)
            
            # DETAIL 처리
            if detail:
                detail_chunks = self._chunk_text_preserving_sentences(detail, self.MAX_LENGTH)
                result.extend(detail_chunks)
                
        else:
            # 폴백: 전체 텍스트를 문장 단위로 분할
            print("[TwitterAdapter] No HOOK/DETAIL markers found, using sentence-aware split")
            result = self._chunk_text_preserving_sentences(content, self.MAX_LENGTH)
            
        # 최대 길이 제한 (스레드 개수)
        if len(result) > self.MAX_THREAD_LENGTH:
            print(f"[TwitterAdapter] Truncating {len(result)} chunks to {self.MAX_THREAD_LENGTH}")
            result = result[:self.MAX_THREAD_LENGTH]
            
        print(f"[TwitterAdapter] Final chunks: {[len(c) for c in result]}")
        return result
        


