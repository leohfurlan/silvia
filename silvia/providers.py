"""Provider adapters. Credentials are resolved only at the network boundary."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

from silvia.core import DomainError
from silvia.security import Redactor


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    endpoint: str
    model: str
    credential_ref: str = ""
    timeout: int = 900
    model_class: str = "standard"
    cost_policy: str = "paid"
    adapter: str = "langchain"
    input_per_million: float | None = None
    output_per_million: float | None = None
    max_output_tokens: int = 4096

    def __post_init__(self):
        url = urlparse(self.endpoint)
        if not self.model or url.username or url.password or url.query or url.fragment or not url.hostname:
            raise DomainError("configuration", "Provider needs a model and endpoint without embedded credentials.")
        if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise DomainError("configuration", "Remote providers require HTTPS; HTTP is allowed only on loopback.")
        if self.cost_policy not in {"paid", "free", "local"} or self.adapter not in {"langchain", "openai-compatible", "responses"} or self.timeout <= 0 or self.max_output_tokens <= 0:
            raise DomainError("configuration", "Invalid provider policy or limits.")
        if self.cost_policy == "local" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise DomainError("configuration", "A local cost policy requires a loopback endpoint.")


@dataclass(frozen=True)
class ProviderReply:
    content: str
    tool_calls: tuple[dict, ...]
    usage: dict


class Provider(Protocol):
    async def invoke(self, messages: list[dict], tools: list[dict], max_tokens: int) -> ProviderReply: ...
    async def request_stop(self) -> bool: ...


def credential(reference: str, redactor: Redactor) -> str:
    if not reference:
        return ""
    if reference.startswith("env:"):
        value = os.environ.get(reference[4:], "")
    elif reference.startswith("keyring:"):
        import keyring
        value = keyring.get_password("SilvIA", reference[8:]) or ""
    else:
        raise DomainError("configuration", "Credential reference must use env: or keyring:.")
    if not value:
        raise DomainError("credential-unavailable", "Referenced credential is unavailable.", "Set the referenced environment variable or Windows credential; never include it in a session.")
    redactor.register(value)
    return value


class OpenAICompatibleProvider:
    def __init__(self, profile: ProviderProfile, redactor: Redactor):
        self.profile, self.redactor = profile, redactor
        self._client = None

    async def request_stop(self) -> bool:
        if self._client is None or self._client.is_closed:
            return False
        await self._client.aclose()
        return True

    async def invoke(self, messages: list[dict], tools: list[dict], max_tokens: int) -> ProviderReply:
        key = credential(self.profile.credential_ref, self.redactor)
        headers = {"Authorization": "Bearer " + key} if key else {}
        payload = {"model": self.profile.model, "messages": messages, "max_tokens": max_tokens, "stream": False}
        if tools:
            payload["tools"] = tools
        try:
            async with httpx.AsyncClient(timeout=self.profile.timeout, follow_redirects=False, trust_env=False) as client:
                self._client = client
                response = await client.post(self.profile.endpoint.rstrip("/") + "/chat/completions", json=payload, headers=headers)
            if response.status_code != 200:
                raise DomainError("provider", f"Provider returned HTTP {response.status_code}.", "Inspect the provider profile and availability.", transient=response.status_code in {429, 503})
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise DomainError("provider-incomplete", "Provider response did not finish normally.")
            message = choice["message"]
            return ProviderReply(message.get("content") or "", tuple(message.get("tool_calls") or []), data.get("usage") or {})
        except httpx.TimeoutException as exc:
            raise DomainError("timeout", "Provider response is uncertain after timeout.") from exc
        except httpx.TransportError as exc:
            raise DomainError("provider-uncertain", "Provider connection ended without a confirmed result.") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise DomainError("provider-invalid", "Provider response does not match the configured protocol.") from exc


class LangChainProvider:
    def __init__(self, profile: ProviderProfile, redactor: Redactor):
        self.profile, self.redactor = profile, redactor

    async def request_stop(self) -> bool:
        # LangChain does not expose a portable cooperative transport close.
        return False

    async def invoke(self, messages: list[dict], tools: list[dict], max_tokens: int) -> ProviderReply:
        from langchain_openai import ChatOpenAI
        import openai
        key = credential(self.profile.credential_ref, self.redactor)
        model = ChatOpenAI(model=self.profile.model, base_url=self.profile.endpoint, api_key=key or "local",
                           timeout=self.profile.timeout, max_retries=0, max_tokens=max_tokens)
        if tools:
            model = model.bind_tools(tools)
        try:
            reply = await model.ainvoke(messages)
        except openai.APITimeoutError as exc:
            raise DomainError("timeout", "Provider response is uncertain after timeout.") from exc
        except openai.APIConnectionError as exc:
            raise DomainError("provider-uncertain", "Provider connection ended without confirmation.") from exc
        except openai.APIStatusError as exc:
            raise DomainError("provider", f"Provider returned HTTP {exc.status_code}.", transient=exc.status_code in {429, 503}) from exc
        finish = reply.response_metadata.get("finish_reason")
        if finish and finish not in {"stop", "tool_calls"}:
            raise DomainError("provider-incomplete", "Provider response is truncated or incomplete.")
        calls = tuple({"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}} for c in reply.tool_calls)
        usage = reply.usage_metadata or {}
        return ProviderReply(reply.content if isinstance(reply.content, str) else "", calls,
                             {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"), "total_tokens": usage.get("total_tokens")})


class ResponsesProvider:
    """Responses protocol adapter used by Astra; tool execution stays in AgentRuntime."""
    def __init__(self, profile: ProviderProfile, redactor: Redactor):
        self.profile, self.redactor = profile, redactor
        self._client = None

    async def request_stop(self) -> bool:
        if self._client is None or self._client.is_closed:
            return False
        await self._client.aclose()
        return True

    async def invoke(self, messages: list[dict], tools: list[dict], max_tokens: int) -> ProviderReply:
        key = credential(self.profile.credential_ref, self.redactor)
        inputs = []
        for message in messages:
            if message["role"] == "tool":
                inputs.append({"type": "function_call_output", "call_id": message["tool_call_id"], "output": message["content"]})
            else:
                if message.get("content"):
                    inputs.append({"role": message["role"], "content": message["content"]})
                for call in message.get("tool_calls", []):
                    inputs.append({"type": "function_call", "call_id": call["id"], **call["function"]})
        payload = {"model": self.profile.model, "input": inputs, "max_output_tokens": max_tokens, "store": False}
        if tools:
            payload["tools"] = [{"type": "function", **t["function"]} for t in tools]
        try:
            async with httpx.AsyncClient(timeout=self.profile.timeout, trust_env=False) as client:
                self._client = client
                response = await client.post(self.profile.endpoint.rstrip("/") + "/responses", json=payload, headers={"Authorization": "Bearer " + key} if key else {})
            if response.status_code != 200:
                raise DomainError("provider", f"Provider returned HTTP {response.status_code}.", transient=response.status_code in {429, 503})
            value = response.json()
            if value.get("status") != "completed":
                raise DomainError("provider-incomplete", "Responses request did not complete.")
            text, calls = [], []
            for item in value.get("output", []):
                if item.get("type") == "message":
                    text.extend(c["text"] for c in item.get("content", []) if c.get("type") == "output_text")
                elif item.get("type") == "function_call":
                    calls.append({"id": item["call_id"], "type": "function", "function": {"name": item["name"], "arguments": item["arguments"]}})
            usage = value.get("usage") or {}
            return ProviderReply("\n".join(text), tuple(calls), {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"), "total_tokens": usage.get("total_tokens")})
        except httpx.TimeoutException as exc:
            raise DomainError("timeout", "Responses request timed out; reconcile before retry.") from exc
        except httpx.TransportError as exc:
            raise DomainError("provider-uncertain", "Responses connection ended without confirmation.") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise DomainError("provider-invalid", "Invalid Responses envelope.") from exc


def build_provider(profile: ProviderProfile, redactor: Redactor) -> Provider:
    return {"langchain": LangChainProvider, "openai-compatible": OpenAICompatibleProvider, "responses": ResponsesProvider}[profile.adapter](profile, redactor)
