"""Independent chat and embedding ports; no provider errors/bodies reach the UI."""

import asyncio
import hashlib
import json
import math
from typing import Protocol

import httpx

from rule_u.config import Settings


class ProviderError(Exception):
    pass


class ChatProvider(Protocol):
    async def generate(self, messages: list[dict[str, str]]) -> str: ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockChat:
    async def generate(self, messages):
        return "[테스트 응답] 질문이 저장되었습니다. 공식 규칙 검색은 아직 연결되지 않아 판정할 수 없습니다."


class MockEmbedding:
    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    async def embed(self, texts):
        # Deterministic test vectors only; never semantic search evidence.
        return [
            [(b / 127.5) - 1 for b in hashlib.shake_256(t.encode()).digest(self.dimensions)]
            for t in texts
        ]


class CompatibleHTTP:
    def __init__(self, base_url, key, timeout, transport=None):
        if not base_url or not key:
            raise ProviderError("provider_not_configured")
        self.base_url = base_url.rstrip("/") + "/"
        self.key = key
        self.timeout = timeout
        self.transport = transport

    async def post(self, path, payload, attempts=2):
        # One retry for transient failures only: latency on the gateway varies widely
        # (the same request has taken 4s and >30s). Client errors are never retried.
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    response = await client.post(
                        self.base_url + path,
                        headers={"Authorization": f"Bearer {self.key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                transient = True
                error = exc
            except httpx.HTTPStatusError as exc:
                transient = exc.response.status_code >= 500 or exc.response.status_code == 429
                error = exc
            except (httpx.HTTPError, ValueError):
                raise ProviderError("provider_call_failed") from None
            if not transient or attempt == attempts - 1:
                raise ProviderError("provider_call_failed") from error
            await asyncio.sleep(1)


class CompatibleChat(CompatibleHTTP):
    def __init__(self, settings: Settings, transport=None):
        super().__init__(
            settings.chat_base_url,
            settings.chat_api_key.get_secret_value(),
            settings.api_timeout_seconds,
            transport,
        )
        self.model = settings.chat_model
        if not self.model:
            raise ProviderError("chat_model_missing")

    async def generate(self, messages):
        data = await self.post("chat/completions", {"model": self.model, "messages": messages})
        try:
            answer = data["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError
            return answer
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("invalid_chat_response") from None


    async def stream(self, messages):
        """Yield text deltas from an OpenAI-compatible SSE stream. Any failure is a
        ProviderError so the caller can fall back to a single non-streamed request."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport, follow_redirects=False
            ) as client:
                async with client.stream(
                    "POST",
                    self.base_url + "chat/completions",
                    headers={"Authorization": f"Bearer {self.key}"},
                    json={"model": self.model, "messages": messages, "stream": True},
                ) as response:
                    response.raise_for_status()
                    if "text/event-stream" not in response.headers.get("content-type", ""):
                        raise ValueError("not_a_stream")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        choice = (json.loads(data).get("choices") or [{}])[0]
                        text = (choice.get("delta") or {}).get("content")
                        if isinstance(text, str) and text:
                            yield text
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("provider_stream_failed") from None


class CompatibleEmbedding(CompatibleHTTP):
    def __init__(self, settings: Settings, transport=None):
        super().__init__(
            settings.embedding_base_url,
            settings.embedding_api_key.get_secret_value(),
            settings.api_timeout_seconds,
            transport,
        )
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        if not self.model:
            raise ProviderError("embedding_model_missing")

    async def embed(self, texts):
        if not texts:
            return []
        data = await self.post(
            "embeddings",
            {
                "model": self.model,
                "input": texts,
                "encoding_format": "float",
            },
        )
        try:
            rows = sorted(data["data"], key=lambda row: row["index"])
            if [r["index"] for r in rows] != list(range(len(texts))):
                raise ValueError
            vectors = [r["embedding"] for r in rows]
            if any(len(v) != self.dimensions for v in vectors):
                raise ValueError
            if any(type(x) not in (int, float) or not math.isfinite(x) for v in vectors for x in v):
                raise ValueError
            return vectors
        except (KeyError, TypeError, ValueError):
            raise ProviderError("invalid_embedding_response_or_dimension") from None


def chat_provider(settings: Settings) -> ChatProvider:
    return MockChat() if settings.chat_provider == "mock" else CompatibleChat(settings)


def embedding_provider(settings: Settings) -> EmbeddingProvider:
    return (
        MockEmbedding(settings.embedding_dimensions)
        if settings.embedding_provider == "mock"
        else CompatibleEmbedding(settings)
    )
