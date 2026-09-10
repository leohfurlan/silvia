"""Redaction at persistence boundaries; raw credentials never enter domain state."""
from __future__ import annotations

import re
from typing import Any

from silvia.core import DomainError

_KEY = re.compile(r"(?i)(password|passwd|secret|api[_-]?key|apikey|authorization|access[_-]?token|refresh[_-]?token|private[_-]?key)")
_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----.*?-----END (?:[A-Z ]*PRIVATE KEY)-----", re.S),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/=_\-.]+"),
    re.compile(r"(?i)(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{16,})"),
    re.compile(r"(?im)\b[A-Z0-9_]*(?:API_?KEY|APIKEY|TOKEN|PASSWORD|SECRET)[A-Z0-9_]*\s*[=:]\s*[^\r\n,}]+"),
    re.compile(r"(?i)https?://[^/\s:@]+:[^/\s@]+@"),
)


class Redactor:
    def __init__(self):
        self._secrets: set[str] = set()

    def register(self, secret: str) -> None:
        if secret:
            self._secrets.add(secret)

    def text(self, text: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        for pattern in _PATTERNS:
            text = pattern.sub("[REDACTED]", text)
        return text

    def clean(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {str(k): "[REDACTED]" if _KEY.search(str(k)) and not str(k).endswith("_ref") else self.clean(v)
                    for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        return value

    def reject_secret(self, text: str) -> None:
        if self.text(text) != text:
            raise DomainError("secret-detected", "Sensitive content was rejected before persistence.")
