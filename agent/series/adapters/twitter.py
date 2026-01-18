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
    
    def publish(self, content: str, images: List[str], config: Dict) -> Dict:
        format_type = config.get('format', 'single')
        
        # 1. 콘텐츠 분할 (스레드)
        chunks = self._split_content(content)
        
        print(f"[TwitterAdapter] Publishing {len(chunks)} tweets (images={len(images)})...")
        
        # 2. 순차 게시
        first_tweet_id = None
        reply_to = None
        
        for i, chunk in enumerate(chunks):
            # 첫 트윗에만 이미지 첨부 (설정에 따라 변경 가능)
            media = images if i == 0 else []
            
            try:
                tweet_id = post_tweet(chunk, media_files=media, reply_to=reply_to)
                if i == 0:
                    first_tweet_id = tweet_id
                
                reply_to = tweet_id
                
                # 봇 감지 방지용 딜레이 (마지막 트윗 제외)
                if i < len(chunks) - 1:
                    time.sleep(2)
                    
            except Exception as e:
                print(f"[TwitterAdapter] Failed to publish tweet {i+1}/{len(chunks)}: {e}")
                # 중간에 실패하면 멈춤 (나중에 재시도 로직 추가 필요)
                break
                
        return {"id": first_tweet_id, "platform": "twitter"}

    def _split_content(self, content: str) -> List[str]:
        """
        긴 글을 트윗 길이로 분할
        (단순 분할보다는 문단/문장 단위로 끊는 것이 좋음)
        """
        # 간단한 구현: 줄바꿈 기준으로 나누고 결합
        paragraphs = content.split('\n')
        chunks = []
        current_chunk = ""
        
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
                
            if len(current_chunk) + len(p) + 1 < self.MAX_LENGTH:
                current_chunk += ("\n" + p).strip()
            else:
                chunks.append(current_chunk)
                current_chunk = p
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
