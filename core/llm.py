"""
LLM Client
멀티 프로바이더 LLM 클라이언트 (Gemini, OpenAI, Anthropic)
Multi-provider LLM client with unified interface
"""
import os
from abc import ABC, abstractmethod
from typing import Optional
from config.settings import settings


class BaseLLMClient(ABC):
    """LLM 클라이언트 추상 클래스"""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", model: Optional[str] = None) -> str:
        """텍스트 생성"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """프로바이더 이름"""
        pass


class GeminiClient(BaseLLMClient):
    """Google Gemini (API or Vertex AI)"""

    def __init__(self):
        from google import genai

        self.client = None
        self.model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash')
        self.backend = None

        if getattr(settings, 'USE_VERTEX_AI', False):
            self._init_vertex_ai(genai)
        elif getattr(settings, 'GEMINI_API_KEY', None):
            self._init_gemini_api(genai)
        else:
            print("[GEMINI] No API key or Vertex AI config!")

    def _init_gemini_api(self, genai):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.backend = "gemini_api"
        print("[GEMINI API] initialized")

    def _init_vertex_ai(self, genai):
        if getattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS', None):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

        self.client = genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION
        )
        self.backend = "vertex_ai"
        print(f"[VERTEX AI] initialized (project={settings.GCP_PROJECT_ID})")

    def generate(self, prompt: str, system_prompt: str = "", model: Optional[str] = None) -> str:
        if not self.client:
            return "Error: LLM not initialized."

        # 시스템 프롬프트와 사용자 프롬프트를 명확하게 구분하여 전달
        if system_prompt:
            full_prompt = f"[시스템 지시]\n{system_prompt}\n\n[사용자 요청]\n{prompt}"
        else:
            full_prompt = prompt
            
        target_model = model or self.model_name

        try:
            response = self.client.models.generate_content(
                model=target_model,
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            print(f"[GEMINI] Generation failed: {e}")
            return f"Error: {e}"

    @property
    def provider_name(self) -> str:
        return f"gemini ({self.backend})"


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT"""

    def __init__(self):
        try:
            from openai import OpenAI
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if not api_key:
                print("[OPENAI] No API key!")
                self.client = None
                return
            self.client = OpenAI(api_key=api_key)
            self.model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
            print(f"[OPENAI] initialized (model={self.model_name})")
        except ImportError:
            print("[OPENAI] openai package not installed")
            self.client = None

    def generate(self, prompt: str, system_prompt: str = "", model: Optional[str] = None) -> str:
        if not self.client:
            return "Error: OpenAI not initialized."

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=model or self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[OPENAI] Generation failed: {e}")
            return f"Error: {e}"

    @property
    def provider_name(self) -> str:
        return "openai"


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude"""

    def __init__(self):
        try:
            from anthropic import Anthropic
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                print("[ANTHROPIC] No API key!")
                self.client = None
                return
            self.client = Anthropic(api_key=api_key)
            self.model_name = getattr(settings, 'ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
            print(f"[ANTHROPIC] initialized (model={self.model_name})")
        except ImportError:
            print("[ANTHROPIC] anthropic package not installed")
            self.client = None

    def generate(self, prompt: str, system_prompt: str = "", model: Optional[str] = None) -> str:
        if not self.client:
            return "Error: Anthropic not initialized."

        try:
            response = self.client.messages.create(
                model=model or self.model_name,
                max_tokens=1024,
                system=system_prompt if system_prompt else "",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"[ANTHROPIC] Generation failed: {e}")
            return f"Error: {e}"

    @property
    def provider_name(self) -> str:
        return "anthropic"


def create_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """설정에 따라 LLM 클라이언트 생성"""
    provider = provider or getattr(settings, 'LLM_PROVIDER', 'gemini')

    clients = {
        'gemini': GeminiClient,
        'openai': OpenAIClient,
        'anthropic': AnthropicClient,
    }

    if provider not in clients:
        print(f"[LLM] Unknown provider: {provider}, falling back to gemini")
        provider = 'gemini'

    return clients[provider]()


# Global instance
llm_client = create_llm_client()
