"""
TLS Fingerprint Patch for twikit
curl_cffi를 사용하여 브라우저 TLS fingerprint 흉내내기

Usage:
    import agent.platforms.twitter.api.tls_patch  # 맨 먼저 import
    from twikit import Client  # 그 다음 twikit import
"""
import asyncio
from typing import Any, Optional, AsyncGenerator
from curl_cffi.requests import AsyncSession
from http.cookiejar import Cookie
import json

# 브라우저 impersonate 옵션
BROWSER_IMPERSONATE = "chrome120"


class FakeCookie:
    """httpx Cookie 호환"""
    def __init__(self, name: str, value: str, domain: str = ""):
        self.name = name
        self.value = value
        self.domain = domain


class CookieJar(dict):
    """httpx.Cookies 호환 래퍼 - dict 상속으로 dict() 변환 지원"""

    def __init__(self):
        super().__init__()
        self.jar = []  # twikit이 이걸 iterate함

    def _update_jar(self):
        self.jar = [FakeCookie(k, v) for k, v in self.items()]

    def set(self, name: str, value: str, domain: str = ""):
        self[name] = value
        self._update_jar()

    def get(self, name: str, default=None):
        return super().get(name, default)

    def clear(self):
        super().clear()
        self.jar = []

    def update(self, cookies=None, **kwargs):
        if cookies is None:
            cookies = {}
        if isinstance(cookies, dict):
            super().update(cookies)
        elif isinstance(cookies, (list, tuple)):
            for item in cookies:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    self[item[0]] = item[1]
        elif isinstance(cookies, str):
            import json
            try:
                parsed = json.loads(cookies)
                if isinstance(parsed, dict):
                    super().update(parsed)
            except:
                pass
        super().update(kwargs)
        self._update_jar()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._update_jar()


class FakeTransport:
    """proxy getter/setter용 가짜 트랜스포트"""
    def __init__(self, proxy_url=None):
        self._proxy_url = proxy_url
        if proxy_url:
            self._pool = type('Pool', (), {'_proxy_url': proxy_url})()
        else:
            self._pool = None


class CurlCffiResponse:
    """httpx.Response 호환 래퍼"""

    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.headers = dict(response.headers) if response.headers else {}
        self.text = response.text
        self.content = response.content

    def json(self):
        return self._response.json()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}: {self.text[:200]}")


class CurlCffiTransport:
    """
    curl_cffi를 httpx.AsyncClient 인터페이스로 래핑
    twikit이 기대하는 메서드들을 구현
    """

    def __init__(self, proxy: Optional[str] = None, **kwargs):
        self._proxy = proxy
        self._session: Optional[AsyncSession] = None
        self._cookies = CookieJar()
        # proxy getter/setter용
        self._mounts = {}
        if proxy:
            self._mounts['all://'] = FakeTransport(proxy)

    @property
    def cookies(self):
        return self._cookies

    @cookies.setter
    def cookies(self, value):
        """twikit이 cookies = list(items) 하는 것 처리"""
        if isinstance(value, CookieJar):
            self._cookies = value
        elif isinstance(value, dict):
            self._cookies.clear()
            self._cookies.update(value)
        elif isinstance(value, list):
            # list of tuples: [(key, value), ...]
            self._cookies.clear()
            for item in value:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    self._cookies[item[0]] = item[1]
        else:
            self._cookies = CookieJar()
            self._cookies.update(value)

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(
                impersonate=BROWSER_IMPERSONATE,
                proxy=self._proxy
            )
        return self._session

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        cookies: Optional[dict] = None,
        data: Any = None,
        json: Any = None,
        files: Any = None,
        content: Any = None,
        timeout: Any = None,
        **kwargs
    ):
        session = await self._get_session()

        # 쿠키 병합
        merged_cookies = dict(self.cookies.items())
        if cookies:
            merged_cookies.update(cookies)

        # content -> data 변환
        if content is not None and data is None:
            data = content

        try:
            response = await session.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                cookies=merged_cookies,
                data=data,
                json=json,
                files=files,
                timeout=timeout if timeout else 30,
            )
        except Exception as e:
            raise Exception(f"curl_cffi request failed: {e}")

        # 응답 쿠키 저장
        if hasattr(response, 'cookies'):
            for name, value in response.cookies.items():
                self.cookies.set(name, value)

        return CurlCffiResponse(response)

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs):
        """스트리밍 지원 (간단 구현)"""
        # curl_cffi의 스트리밍은 다르게 동작하므로 일단 일반 요청으로 대체
        response = await self.request(method, url, **kwargs)
        return StreamContext(response)

    async def aclose(self):
        if self._session:
            await self._session.close()
            self._session = None


class StreamContext:
    """async with 컨텍스트용 스트림 래퍼"""
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *args):
        pass


def patch_twikit():
    """
    twikit의 httpx.AsyncClient를 curl_cffi로 교체
    """
    import twikit.client.client as twikit_client
    from httpx._utils import URLPattern

    _original_init = twikit_client.Client.__init__

    def patched_init(self, language='en-US', proxy=None, captcha_solver=None,
                     user_agent=None, **kwargs):
        # curl_cffi 트랜스포트 사용 (http 먼저 설정)
        self.http = CurlCffiTransport(proxy=proxy)

        # 기존 초기화 (proxy setter 우회)
        self.language = language
        self._proxy = proxy
        self.captcha_solver = captcha_solver
        if captcha_solver is not None:
            captcha_solver.client = self

        self._token = twikit_client.TOKEN
        self._user_id = None
        self._user_agent = user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15'
        self._act_as = None

        # GQL, V11 클라이언트
        from twikit.client.gql import GQLClient
        from twikit.client.v11 import V11Client
        from twikit.x_client_transaction import ClientTransaction

        self.client_transaction = ClientTransaction()
        self.gql = GQLClient(self)
        self.v11 = V11Client(self)

    # proxy property 오버라이드
    @property
    def patched_proxy(self):
        return self._proxy

    @patched_proxy.setter
    def patched_proxy(self, url):
        self._proxy = url
        if hasattr(self, 'http') and self.http:
            self.http._proxy = url

    twikit_client.Client.__init__ = patched_init
    twikit_client.Client.proxy = patched_proxy
    print(f"[TLS_PATCH] ✅ twikit patched with curl_cffi ({BROWSER_IMPERSONATE} fingerprint)")


# 모듈 로드 시 자동 패치
patch_twikit()
