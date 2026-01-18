"""
Text Utilities - Platform Agnostic
텍스트 분석 및 처리 공통 유틸리티
"""
import re
from typing import Set, List


def extract_keywords(text: str) -> Set[str]:
    """텍스트에서 키워드 추출 (조사 제거 + 2글자 이상)"""
    words = re.findall(r'[가-힣a-zA-Z]{2,}', text)

    stopwords = {
        '오늘', '문득', '그게', '이제', '근데', '그런', '어떤', '뭔가', '진짜', '정말',
        '그냥', '너무', '아주', '매우', '조금', '좀', '많이', '약간', '이런', '저런',
        '하는', '하고', '해서', '했는데', '했어요', '거든요', '같아요', '있어요', '없어요',
        '생각', '느낌', '기분', '마음', '것', '거', '뭐', '왜', '어떻게'
    }

    josa_pattern = r'(이|가|은|는|을|를|의|에|에서|로|으로|와|과|랑|이랑|도|만|까지|부터|처럼|같이|라고|이라고|라는|이라는|란|이란|들|했|하다|하고|해서|에요|예요|이에요|거든요|잖아요|네요|죠|이죠)$'

    keywords = set()
    for w in words:
        if w in stopwords or len(w) < 2:
            continue
        cleaned = re.sub(josa_pattern, '', w)
        if len(cleaned) >= 2:
            keywords.add(cleaned)

    return keywords


def extract_ngrams(text: str, n: int = 3) -> Set[str]:
    """텍스트에서 n-gram 추출 (공백 제거)"""
    text = re.sub(r'[^가-힣a-zA-Z]', '', text)
    if len(text) < n:
        return set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def calculate_similarity(text1: str, text2: str) -> float:
    """키워드 + n-gram 기반 유사도

    두 가지 기준:
    1. 키워드 Jaccard similarity
    2. 공통 4-gram 개수 기반 (5개 이상이면 유사)
    """
    kw1 = extract_keywords(text1)
    kw2 = extract_keywords(text2)

    ng1 = extract_ngrams(text1, 4)
    ng2 = extract_ngrams(text2, 4)

    kw_sim = 0.0
    if kw1 and kw2:
        common_kw = kw1 & kw2
        union = len(kw1 | kw2)
        kw_sim = len(common_kw) / union if union > 0 else 0.0
        if len(common_kw) >= 3:
            kw_sim = max(kw_sim, 0.35)

    ng_sim = 0.0
    if ng1 and ng2:
        common_ng = ng1 & ng2
        if len(common_ng) >= 8:
            ng_sim = 0.5
        elif len(common_ng) >= 5:
            ng_sim = 0.35
        elif len(common_ng) >= 3:
            ng_sim = 0.2

    return max(kw_sim, ng_sim)
