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
        else:
            # 폴백: 기존 로직 (문단 기반 분할)
            print("[TwitterAdapter] No HOOK/DETAIL markers found, using fallback split")
            paragraphs = content.split('\n')
            chunks = []
            current = ""
            
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                potential = current + ("\n" if current else "") + p
                if len(potential) < self.MAX_LENGTH:
                    current = potential
                else:
                    if current:
                        chunks.append(current)
                    current = p
            if current:
                chunks.append(current)
            
            if len(chunks) > self.MAX_THREAD_LENGTH:
                chunks = chunks[:self.MAX_THREAD_LENGTH]
            
            print(f"[TwitterAdapter] Fallback split into {len(chunks)} chunks")
            return chunks
        
        # HOOK/DETAIL이 있으면 정확히 2개로 반환
        result = []
        
        # HOOK은 무조건 첫 번째 (이미지와 함께)
        if hook:
            # HOOK이 너무 길면 자르기
            if len(hook) > self.MAX_LENGTH:
                hook = hook[:self.MAX_LENGTH - 3] + "..."
            result.append(hook)
        
        # DETAIL은 두 번째 (댓글로)
        if detail:
            # DETAIL이 너무 길면 잘라서 여러 청크로
            if len(detail) > self.MAX_LENGTH:
                # 문장 단위로 분할
                sentences = detail.replace('... ', '...\n').replace('. ', '.\n').split('\n')
                current = ""
                for s in sentences:
                    s = s.strip()
                    if not s:
                        continue
                    potential = current + (" " if current else "") + s
                    if len(potential) < self.MAX_LENGTH:
                        current = potential
                    else:
                        if current:
                            result.append(current)
                        current = s
                if current:
                    result.append(current)
            else:
                result.append(detail)
        
        # 최대 길이 제한
        if len(result) > self.MAX_THREAD_LENGTH:
            print(f"[TwitterAdapter] Truncating {len(result)} to {self.MAX_THREAD_LENGTH}")
            result = result[:self.MAX_THREAD_LENGTH]
        
        print(f"[TwitterAdapter] Final chunks: {[len(c) for c in result]}")
        return result

