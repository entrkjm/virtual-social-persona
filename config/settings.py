import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # ===========================================
    # 인증 정보 (.env에서 로드)
    # ===========================================
    GAME_API_KEY = os.getenv("GAME_API_KEY")
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

    THREADS_USERNAME = os.getenv("THREADS_USERNAME")
    THREADS_PASSWORD = os.getenv("THREADS_PASSWORD")

    # LLM 설정
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini | openai | anthropic

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.0-flash-exp")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
    USE_VIRTUAL_SDK = os.getenv("USE_VIRTUAL_SDK", "true").lower() == "true"
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "vaiv-observatory")
    GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcp-key.json")

    # Vision & Image Gen
    IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-001")
    GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash-exp")

    # Agent 모드 설정 (normal | test | aggressive)
    AGENT_MODE = os.getenv("AGENT_MODE", "normal")

    # 데이터 저장 경로
    DATA_DIR = os.getenv("DATA_DIR", "data")
    MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", os.path.join(DATA_DIR, "memory.db"))
    CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(DATA_DIR, "chroma"))

    # ===========================================
    # 포스팅/시스템 설정 (하드코딩, 추후 페르소나 이관 가능)
    # ===========================================
    PROB_REGRET = 0.30
    PROB_FLASH = 0.70
    PROB_FLASH_REINFORCED = 0.80
    PROB_MOOD_BURST = 0.30
    PROB_RANDOM_RECALL = 0.05
    POST_MIN_INTERVAL = 60
    CONSOLIDATION_INTERVAL = 1

settings = Settings()
