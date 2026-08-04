from __future__ import annotations

import logging
from typing import Any

import httpx

from app.parsing.prompt import prompt_version, static_cache_text

logger = logging.getLogger(__name__)

CACHE_DISPLAY_PREFIX = "chontak-parser-"
DEFAULT_CACHE_TTL_SECONDS = 604800
_BASE = "https://generativelanguage.googleapis.com/v1beta"


def cache_display_name(version: str) -> str:
    return f"{CACHE_DISPLAY_PREFIX}{version}"


class GooglePromptCache:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client
        self._local_name: str | None = None
        self._local_version: str | None = None

    def get_cached_name(self) -> str | None:
        if self._local_version != prompt_version():
            return None
        return self._local_name

    def clear_local(self) -> None:
        self._local_name = None
        self._local_version = None

    def _params(self) -> dict[str, str]:
        return {"key": self._api_key}

    async def ensure_cache(self) -> str | None:
        try:
            return await self._ensure_cache()
        except Exception:
            logger.exception("prompt cache ensure failed")
            return None

    async def _ensure_cache(self) -> str:
        version = prompt_version()
        wanted = cache_display_name(version)
        if self._local_name and self._local_version == version:
            return self._local_name

        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            listed = await self._list(client)
            current = None
            for item in listed:
                name = item.get("name")
                display = item.get("displayName") or ""
                if not isinstance(name, str):
                    continue
                if not display.startswith(CACHE_DISPLAY_PREFIX):
                    continue
                if display == wanted:
                    current = name
                else:
                    await self._delete(client, name)
            if current is None:
                current = await self._create(client, wanted)
            self._local_name = current
            self._local_version = version
            return current
        finally:
            if owns:
                await client.aclose()

    async def delete_installation_caches(self) -> None:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            for item in await self._list(client):
                name = item.get("name")
                display = item.get("displayName") or ""
                if isinstance(name, str) and display.startswith(CACHE_DISPLAY_PREFIX):
                    await self._delete(client, name)
            self.clear_local()
        finally:
            if owns:
                await client.aclose()

    async def create_cache(self) -> str:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            name = await self._create(client, cache_display_name(prompt_version()))
            self._local_name = name
            self._local_version = prompt_version()
            return name
        finally:
            if owns:
                await client.aclose()

    async def extend_ttl(self, name: str, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.patch(
                f"{_BASE}/{name}",
                params=self._params(),
                headers={"Content-Type": "application/json"},
                json={"ttl": f"{ttl_seconds}s"},
            )
            if response.status_code >= 400:
                logger.warning("cache TTL extend failed: %s", response.status_code)
        finally:
            if owns:
                await client.aclose()

    async def _list(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get(f"{_BASE}/cachedContents", params=self._params())
        response.raise_for_status()
        data = response.json()
        items = data.get("cachedContents") or []
        return items if isinstance(items, list) else []

    async def _delete(self, client: httpx.AsyncClient, name: str) -> None:
        response = await client.delete(f"{_BASE}/{name}", params=self._params())
        if response.status_code >= 400 and response.status_code != 404:
            logger.warning("cache delete failed for %s: %s", name, response.status_code)

    async def _create(self, client: httpx.AsyncClient, display_name: str) -> str:
        response = await client.post(
            f"{_BASE}/cachedContents",
            params=self._params(),
            headers={"Content-Type": "application/json"},
            json={
                "model": f"models/{self._model}",
                "displayName": display_name,
                "systemInstruction": {
                    "parts": [{"text": static_cache_text()}]
                },
                "ttl": f"{DEFAULT_CACHE_TTL_SECONDS}s",
            },
        )
        response.raise_for_status()
        data = response.json()
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("cache create returned no name")
        return name
