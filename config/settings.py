import os
import yaml
from dotenv import load_dotenv

load_dotenv()

def _load_behavior_config():
    """behavior.yaml 로드"""
    config_path = os.path.join(os.path.dirname(__file__), "behavior.yaml")
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

_behavior = _load_behavior_config()

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

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
    USE_VIRTUAL_SDK = os.getenv("USE_VIRTUAL_SDK", "true").lower() == "true"
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "vaiv-observatory")
    GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcp-key.json")

    # Agent 모드 설정 (normal | test | aggressive)
    AGENT_MODE = os.getenv("AGENT_MODE", "normal")

    # 데이터 저장 경로
    DATA_DIR = os.getenv("DATA_DIR", "data")
    MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", os.path.join(DATA_DIR, "memory.db"))
    CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(DATA_DIR, "chroma"))

    # ===========================================
    # 행동 설정 (behavior.yaml에서 로드)
    # ===========================================
    _step = _behavior.get('step_interval', {})
    STEP_INTERVAL_MIN = _step.get('min', 30)
    STEP_INTERVAL_MAX = _step.get('max', 300)

    _action = _behavior.get('action_probability', {})
    PROB_LURK = _action.get('lurk', 0.40)
    PROB_LIKE_ONLY = _action.get('like_only', 0.30)
    PROB_COMMENT = _action.get('comment', 0.25)
    PROB_LIKE_AND_COMMENT = _action.get('like_and_comment', 0.05)
    PROB_REGRET = _action.get('regret', 0.30)

    _posting = _behavior.get('posting_trigger', {})
    PROB_FLASH = _posting.get('flash', 0.70)
    PROB_FLASH_REINFORCED = _posting.get('flash_reinforced', 0.80)
    PROB_MOOD_BURST = _posting.get('mood_burst', 0.30)
    PROB_RANDOM_RECALL = _posting.get('random_recall', 0.05)

    POST_MIN_INTERVAL = _behavior.get('post_min_interval', 60)
    CONSOLIDATION_INTERVAL = _behavior.get('consolidation_interval', 1)

settings = Settings()
