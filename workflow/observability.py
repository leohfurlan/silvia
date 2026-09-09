"""Live and structured observability for workflow runs."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


@dataclass(frozen=True)
class WorkflowEvent:
    kind: str
    role: str = "controller"
    model: str = ""
    task_id: str = ""
    message: str = ""
    payload: dict[str, object] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class Observer:
    async def emit(self, event: WorkflowEvent) -> None:
        raise NotImplementedError


class NullObserver(Observer):
    async def emit(self, event: WorkflowEvent) -> None:
        return None


def _display_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _safe_tool_output(value: Any, limit: int = 1000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = re.sub(r"(?im)^\s*(APIKEY_B_AI|BAI_API_KEY|OPENAI_API_KEY|SECRET_KEY|[A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY)[A-Z0-9_]*)\s*=.*$", r"\1=[REDACTED]", text)
    text = re.sub(r"-----BEGIN [^-]+ PRIVATE KEY-----.*?-----END [^-]+ PRIVATE KEY-----", "[PRIVATE_KEY_REDACTED]", text, flags=re.DOTALL)
    text = text.replace("\r", "").replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "… [truncated]"
    return text


class LiveObserver(Observer):
    """Render timestamped progress without exposing hidden model reasoning."""

    def __init__(self, stream: TextIO | None = None):
        self.stream = stream or sys.stderr
        self._lock = asyncio.Lock()
        self._open_streams: set[str] = set()

    async def emit(self, event: WorkflowEvent) -> None:
        label = event.role if not event.task_id else f"{event.role}:{event.task_id}"
        stamp = _display_timestamp()
        async with self._lock:
            if event.kind == "token":
                if label not in self._open_streams:
                    self.stream.write(f"[{stamp}] [{label}] retorno: ")
                    self._open_streams.add(label)
                self.stream.write(event.message)
            else:
                if label in self._open_streams:
                    self.stream.write("\n")
                    self._open_streams.discard(label)
                if event.kind == "agent_started":
                    self.stream.write(f"[{stamp}] [{label}] iniciado\n")
                elif event.kind == "agent_finished":
                    self.stream.write(f"[{stamp}] [{label}] concluído\n")
                elif event.kind == "agent_failed":
                    self.stream.write(f"[{stamp}] [{label}] FALHOU: {event.message}\n")
                elif event.kind == "stage":
                    self.stream.write(f"[{stamp}] [{label}] {event.message}\n")
                elif event.kind == "tool_started":
                    self.stream.write(f"[{stamp}] [{label}] ferramenta iniciada: {event.message}\n")
                elif event.kind == "tool_finished":
                    result = event.payload.get("return", "")
                    self.stream.write(f"[{stamp}] [{label}] retorno de {event.message}: {result}\n")
            self.stream.flush()


class JsonlObserver(Observer):
    """Persist operational events when the caller explicitly requests a file."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def emit(self, event: WorkflowEvent) -> None:
        line = json.dumps(event.as_dict(), ensure_ascii=False) + "\n"
        async with self._lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)


class CompositeObserver(Observer):
    def __init__(self, observers: list[Observer]):
        self.observers = tuple(observers)

    async def emit(self, event: WorkflowEvent) -> None:
        await asyncio.gather(*(observer.emit(event) for observer in self.observers))
