"""
Platform Adapter Base & Twitter Adapter
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import time
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
    TWEET_DELAY = 15  # 트윗 사이 15초 딜레이
    
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
                
                # 봇 감지 방지용 딜레이 (마지막 트윗 제외)
                if i < len(chunks) - 1:
                    print(f"[TwitterAdapter] Waiting {self.TWEET_DELAY}s before next tweet...")
                    time.sleep(self.TWEET_DELAY)
                    
            except Exception as e:
                print(f"[TwitterAdapter] Failed to publish tweet {i+1}/{len(chunks)}: {e}")
                # 중간에 실패하면 멈춤 (나중에 재시도 로직 추가 필요)
                break
                
        return {"id": first_tweet_id, "platform": "twitter"}

    def _split_content(self, content: str) -> List[str]:
        """
        긴 글을 트윗 길이로 분할
        첫 번째 청크는 항상 이미지와 함께 게시되므로 내용이 있어야 함
        """
        if not content or not content.strip():
            return []
            
        # 줄바꿈 기준으로 나누고 결합
        paragraphs = content.split('\n')
        chunks = []
        current_chunk = ""
        
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
                
            # 현재 청크에 추가할 수 있는지 확인
            potential = current_chunk + ("\n" if current_chunk else "") + p
            
            if len(potential) < self.MAX_LENGTH:
                current_chunk = potential
            else:
                # 현재 청크가 있으면 저장하고 새로 시작
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = p
                
        # 마지막 청크 추가
        if current_chunk:
            chunks.append(current_chunk)
        
        # 첫 번째 청크가 너무 짧으면 다음과 병합 시도
        if len(chunks) > 1 and len(chunks[0]) < 50:
            merged = chunks[0] + "\n" + chunks[1]
            if len(merged) < self.MAX_LENGTH:
                chunks = [merged] + chunks[2:]
            
        # 최대 스레드 길이 제한
        if len(chunks) > self.MAX_THREAD_LENGTH:
            print(f"[TwitterAdapter] Truncating {len(chunks)} tweets to {self.MAX_THREAD_LENGTH}")
            chunks = chunks[:self.MAX_THREAD_LENGTH]
        
        print(f"[TwitterAdapter] Split into {len(chunks)} chunks: {[len(c) for c in chunks]}")
            
        return chunks

