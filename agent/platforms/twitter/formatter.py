"""
Twitter Platform Formatter
트위터 특화 텍스트 포맷팅 로직
"""
import re
from typing import List


def twitter_weighted_len(text: str) -> int:
    """Twitter 가중치 글자수 (한글/한자/일본어 = 2, 나머지 = 1)"""
    count = 0
    for char in text:
        if '\u1100' <= char <= '\u11FF' or '\u3130' <= char <= '\u318F' or '\uAC00' <= char <= '\uD7AF':
            count += 2
        elif '\u4E00' <= char <= '\u9FFF' or '\u3040' <= char <= '\u30FF':
            count += 2
        else:
            count += 1
    return count


def contains_forbidden_chars(text: str) -> bool:
    """한자, 일본어 포함 여부 체크"""
    # CJK Unified Ideographs (한자)
    if re.search(r'[\u4e00-\u9fff]', text):
        return True
    # 히라가나
    if re.search(r'[\u3040-\u309f]', text):
        return True
    # 가타카나
    if re.search(r'[\u30a0-\u30ff]', text):
        return True
    return False


def get_forbidden_chars(text: str) -> List[str]:
    """금지 문자 추출"""
    found = []
    hanzi = re.findall(r'[\u4e00-\u9fff]+', text)
    if hanzi:
        found.extend(hanzi)
    hiragana = re.findall(r'[\u3040-\u309f]+', text)
    if hiragana:
        found.extend(hiragana)
    katakana = re.findall(r'[\u30a0-\u30ff]+', text)
    if katakana:
        found.extend(katakana)
    return found


def truncate_to_twitter_limit(text: str, max_weighted: int = 280) -> str:
    """트위터 제한에 맞게 텍스트 자르기"""
    weighted = twitter_weighted_len(text)
    if weighted <= max_weighted:
        return text
    
    # 비율 계산하여 자르기
    target_chars = len(text) * max_weighted // weighted
    return text[:target_chars - 3] + "..."
