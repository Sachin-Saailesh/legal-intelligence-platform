import asyncio
import time
from typing import Any

from openai import AsyncAzureOpenAI, RateLimitError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_langfuse_client: Any = None


def _get_langfuse():
    global _langfuse_client
    if _langfuse_client is None and settings.langfuse_public_key:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except Exception:
            pass
    return _langfuse_client


class AzureEmbeddingClient:
    def __init__(self) -> None:
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_embedding_endpoint,
            api_key=settings.azure_embedding_api_key,
            api_version=settings.azure_embedding_api_version,
        )
        self._deployment = settings.azure_embedding_deployment
        self._batch_size = 100

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        t0 = time.perf_counter()
        response = await self._client.embeddings.create(
            input=[text],
            model=self._deployment,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        tokens = response.usage.total_tokens
        embedding = response.data[0].embedding

        lf = _get_langfuse()
        if lf:
            lf.generation(
                name="embed_text",
                model=self._deployment,
                usage={"total_tokens": tokens},
                metadata={"latency_ms": latency_ms},
            )

        logger.info(
            "embed_text",
            deployment=self._deployment,
            tokens=tokens,
            latency_ms=round(latency_ms, 2),
            dims=len(embedding),
        )
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            embeddings = await self._embed_batch_chunk(batch)
            results.extend(embeddings)
        return results

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _embed_batch_chunk(self, texts: list[str]) -> list[list[float]]:
        t0 = time.perf_counter()
        response = await self._client.embeddings.create(
            input=texts,
            model=self._deployment,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        tokens = response.usage.total_tokens

        lf = _get_langfuse()
        if lf:
            lf.generation(
                name="embed_batch",
                model=self._deployment,
                usage={"total_tokens": tokens},
                metadata={"latency_ms": latency_ms, "batch_size": len(texts)},
            )

        logger.info(
            "embed_batch_chunk",
            deployment=self._deployment,
            batch_size=len(texts),
            tokens=tokens,
            latency_ms=round(latency_ms, 2),
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


class AzureLLMClient:
    def __init__(self) -> None:
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_chat_endpoint,
            api_key=settings.azure_chat_api_key,
            api_version=settings.azure_chat_api_version,
            timeout=120.0,
        )
        self._deployment = settings.azure_chat_deployment

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def complete(
        self,
        system: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        trace_name: str = "llm_complete",
    ) -> str:
        t0 = time.perf_counter()
        all_messages = [{"role": "system", "content": system}] + messages
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = response.usage
        content = response.choices[0].message.content or ""

        lf = _get_langfuse()
        if lf:
            lf.generation(
                name=trace_name,
                model=self._deployment,
                input=all_messages,
                output=content,
                usage={
                    "input": usage.prompt_tokens,
                    "output": usage.completion_tokens,
                    "total": usage.total_tokens,
                },
                metadata={"latency_ms": latency_ms, "temperature": temperature},
            )

        logger.info(
            "llm_complete",
            trace_name=trace_name,
            deployment=self._deployment,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=round(latency_ms, 2),
        )
        return content

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def stream_complete(
        self,
        system: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        trace_name: str = "llm_stream",
    ):
        """Yields string chunks for WebSocket streaming."""
        t0 = time.perf_counter()
        all_messages = [{"role": "system", "content": system}] + messages
        stream = await self._client.chat.completions.create(
            model=self._deployment,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        collected = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                collected.append(delta)
                yield delta

        latency_ms = (time.perf_counter() - t0) * 1000
        full_output = "".join(collected)

        lf = _get_langfuse()
        if lf:
            lf.generation(
                name=trace_name,
                model=self._deployment,
                input=all_messages,
                output=full_output,
                metadata={"latency_ms": latency_ms, "streaming": True},
            )

        logger.info(
            "llm_stream_complete",
            trace_name=trace_name,
            deployment=self._deployment,
            output_chars=len(full_output),
            latency_ms=round(latency_ms, 2),
        )


# Singletons reused across the app
embedding_client = AzureEmbeddingClient()
llm_client = AzureLLMClient()
